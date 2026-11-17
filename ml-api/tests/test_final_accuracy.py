"""11-17: '이 예측, 믿을 만한가요?' = 최종 모델 시험 정확도 (품종 → 품목 → 전체)"""

from app.core import final_accuracy as fa


def test_bucket_by_days():
    assert [fa.bucket(d) for d in (1, 7, 8, 20, 21, 91, 92, 182, 183, 365)] == ["d1", "d1", "d2", "d2", "m1", "m1", "m2", "m2", "m3", "m3"]


def test_item_differs_and_not_band_width():
    a, _ = fa.accuracy("napa_cabbage", "", 3)
    b, _ = fa.accuracy("carrot", "", 3)
    assert a != b                      # 품목마다 다름 (전에는 기간만으로 같은 값)
    assert 40 < b < a < 100


def test_variety_then_item_then_total():
    v, _ = fa.accuracy("napa_cabbage", "napa_cabbage-1", 3)
    i, _ = fa.accuracy("napa_cabbage", "", 3)
    assert v != i
    t, b = fa.accuracy("no_such_item", "", 3)
    assert b == "d1" and t == 77.8    # 전체 1~5거래일
