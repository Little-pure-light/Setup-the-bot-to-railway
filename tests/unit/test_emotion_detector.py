"""modules/emotion_detector.py 單元測試"""
import pytest


CASES = [
    ("我今天真的很開心", "joy"),
    ("我現在好難過", "sadness"),
    ("氣死我了", "anger"),
    ("我有點害怕", "fear"),
    ("謝謝你陪我", "grateful"),
    ("我好累", "tired"),
    ("我看不懂", "confused"),
    ("今天天氣不錯", None),  # 可能 neutral 或 joy（"不錯"/"好" 關鍵詞）
    ("哈哈我快氣死了", "anger"),
]


@pytest.mark.unit
@pytest.mark.parametrize("text,expected", CASES)
def test_dominant_emotion_reasonable(emotion_detector, text, expected):
    result = emotion_detector.analyze_emotion(text)
    assert "dominant_emotion" in result
    assert "confidence" in result
    assert "intensity" in result
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["intensity"] >= 0
    if expected is not None:
        assert result["dominant_emotion"] == expected


@pytest.mark.unit
def test_empty_string_safe(emotion_detector):
    result = emotion_detector.analyze_emotion("")
    assert result["dominant_emotion"] == "neutral"
    assert result["intensity"] >= 0


@pytest.mark.unit
def test_none_like_empty(emotion_detector):
    result = emotion_detector.analyze_emotion(None)  # type: ignore[arg-type]
    assert result["dominant_emotion"] == "neutral"


@pytest.mark.unit
def test_emoji_input_safe(emotion_detector):
    result = emotion_detector.analyze_emotion("😊🎉✨")
    assert result["dominant_emotion"]
    assert result["intensity"] >= 0


@pytest.mark.unit
def test_mixed_chinese_english_safe(emotion_detector):
    result = emotion_detector.analyze_emotion("I am so happy 我超開心 today!!!")
    assert result["dominant_emotion"] == "joy"
    assert 0 <= result["confidence"] <= 1


@pytest.mark.unit
def test_response_style_keys(emotion_detector):
    analysis = emotion_detector.analyze_emotion("謝謝你")
    style = emotion_detector.get_emotion_response_style(analysis)
    for key in ("tone", "emoji_frequency", "empathy_level", "energy_level", "suggested_emojis"):
        assert key in style


@pytest.mark.unit
def test_intensity_not_negative_with_exclaim(emotion_detector):
    result = emotion_detector.analyze_emotion("好開心！！！")
    assert result["intensity"] >= 0
    assert result["dominant_emotion"] == "joy"
