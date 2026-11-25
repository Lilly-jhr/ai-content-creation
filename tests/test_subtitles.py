from pipeline.models import Storyboard
from pipeline.stages import subtitles


def test_chunks_respect_line_limits():
    text = "Nothing I have is mine alone. It is the work of everyone who came before me. " * 2
    for event in subtitles.chunk(text):
        assert 1 <= len(event) <= subtitles.MAX_LINES
        assert all(len(line) <= subtitles.MAX_CHARS for line in event)


def test_events_sit_inside_narration_windows(raw_storyboard):
    sb = Storyboard.model_validate(raw_storyboard)
    timeline = {"shots": [], "end_card": {"start": 0, "duration": 3}, "total": 0}
    t = 0.0
    for s in sb.shots:
        timeline["shots"].append(
            {
                "id": s.id,
                "start": t,
                "duration": 7.0,
                "vo_start": t + 0.5,
                "vo_duration": 5.0,
                "vo_path": "x",
            }
        )
        t += 7.0
    evs = subtitles.events(sb, timeline)
    assert evs and all(b > a for a, b, _ in evs)
    assert all(text.count(r"\N") <= 1 for _, _, text in evs)
    ass = subtitles.ass("9x16", evs)
    assert "PlayResX: 1080" in ass and "Dialogue:" in ass
