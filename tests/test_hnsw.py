import math
import numpy as np
import random
from common import *
from objectbox.query_builder import QueryBuilder


def _find_expected_nn(points: np.ndarray, query: np.ndarray, n: int):
    """ Given a set of points of shape (N, P) and a query of shape (P), finds the n points nearest to query. """

    assert points.ndim == 2 and query.ndim == 1
    assert points.shape[1] == query.shape[0]

    d = np.linalg.norm(points - query, axis=1)  # Euclidean distance
    return np.argsort(d)[:n]


def _test_random_points(num_points: int, num_query_points: int, seed: Optional[int] = None):
    """ Generates random points in a 2d plane; checks the queried NN against the expected. """

    print(f"Test random points; Points: {num_points}, Query points: {num_query_points}, Seed: {seed}")

    k = 10

    if seed is not None:
        np.random.seed(seed)

    points = np.random.rand(num_points, 2).astype(np.float32)

    db = create_test_objectbox()

    # Init and seed DB
    box = objectbox.Box(db, VectorEntity)

    print(f"Seeding DB with {num_points} points...")
    objects = []
    for i in range(points.shape[0]):
        object_ = VectorEntity()
        object_.name = f"point_{i}"
        object_.vector = points[i]
        objects.append(object_)
    box.put(*objects)
    print(f"DB seeded with {box.count()} random points!")

    assert box.count() == num_points

    # Generate a random list of query points
    query_points = np.random.rand(num_query_points, 2).astype(np.float32)

    # Iterate query points, and compare expected result with OBX result
    print(f"Running {num_query_points} searches...")
    for i in range(query_points.shape[0]):
        query_point = query_points[i]

        # Find the ground truth (brute force)
        expected_result = _find_expected_nn(points, query_point, k) + 1  # + 1 because OBX IDs start from 1
        assert len(expected_result) == k

        # Run ANN with OBX
        query_builder = QueryBuilder(db, box)
        query_builder.nearest_neighbors_f32("vector", query_point, k)
        query = query_builder.build()
        obx_result = [id_ for id_, score in query.find_ids_with_scores()]  # Ignore score
        assert len(obx_result) == k

        # We would like at least half of the expected results, to be returned by the search (in any order)
        # Remember: it's an approximate search!
        search_score = len(np.intersect1d(expected_result, obx_result)) / k
        assert search_score >= 0.5  # TODO likely could be increased

    print(f"Done!")


def test_random_points():
    _test_random_points(num_points=100, num_query_points=10, seed=10)
    _test_random_points(num_points=100, num_query_points=10, seed=11)
    _test_random_points(num_points=100, num_query_points=10, seed=12)
    _test_random_points(num_points=100, num_query_points=10, seed=13)
    _test_random_points(num_points=100, num_query_points=10, seed=14)
    _test_random_points(num_points=100, num_query_points=10, seed=15)


def test_combined_nn_search():
    """ Tests NN search combined with regular query conditions, offset and limit. """

    db = create_test_objectbox()

    box = objectbox.Box(db, VectorEntity)

    box.put(VectorEntity(name="Power of red", vector=[1, 1]))
    box.put(VectorEntity(name="Blueberry", vector=[2, 2]))
    box.put(VectorEntity(name="Red", vector=[3, 3]))
    box.put(VectorEntity(name="Blue sea", vector=[4, 4]))
    box.put(VectorEntity(name="Lightblue", vector=[5, 5]))
    box.put(VectorEntity(name="Red apple", vector=[6, 6]))
    box.put(VectorEntity(name="Hundred", vector=[7, 7]))
    box.put(VectorEntity(name="Tired", vector=[8, 8]))
    box.put(VectorEntity(name="Power of blue", vector=[9, 9]))

    assert box.count() == 9

    # Test condition + NN search
    query = box.query() \
        .nearest_neighbors_f32("vector", [4.1, 4.2], 6) \
        .contains_string("name", "red", case_sensitive=False) \
        .build()
    # 4, 5, 3, 6, 2, 7
    # Filtered: 3, 6, 7
    search_results = query.find_with_scores()
    assert len(search_results) == 3
    assert search_results[0][0].name == "Red"
    assert search_results[1][0].name == "Red apple"
    assert search_results[2][0].name == "Hundred"

    # Test offset/limit on find_with_scores (result is ordered by score desc)
    query.offset(1)
    query.limit(1)
    search_results = query.find_with_scores()
    assert len(search_results) == 1
    assert search_results[0][0].name == "Red apple"

    # Regular condition + NN search
    query = box.query() \
        .nearest_neighbors_f32("vector", [9.2, 8.9], 7) \
        .starts_with_string("name", "Blue", case_sensitive=True) \
        .build()

    search_results = query.find_with_scores()
    assert len(search_results) == 1
    assert search_results[0][0].name == "Blue sea"

    # Regular condition + NN search
    query = box.query() \
        .nearest_neighbors_f32("vector", [7.7, 7.7], 8) \
        .contains_string("name", "blue", case_sensitive=False) \
        .build()
    # 8, 7, 9, 6, 5, 4, 3, 2
    # Filtered: 9, 5, 4, 2
    search_results = query.find_ids_with_scores()
    assert len(search_results) == 4
    assert search_results[0][0] == 9
    assert search_results[1][0] == 5
    assert search_results[2][0] == 4
    assert search_results[3][0] == 2

    search_results = query.find_ids()
    assert len(search_results) == 4
    assert search_results[0] == 2
    assert search_results[1] == 4
    assert search_results[2] == 5
    assert search_results[3] == 9

    # Test offset/limit on find_ids (result is ordered by ID asc)
    query.offset(1)
    query.limit(2)
    search_results = query.find_ids()
    assert len(search_results) == 2
    assert search_results[0] == 4
    assert search_results[1] == 5
