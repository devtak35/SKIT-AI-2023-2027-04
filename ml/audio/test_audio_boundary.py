import json
from ml.audio.playback_sync import PlaybackSegment, segment_at
from ml.audio.preprocess import normalize_pcm16le, prepare_pcm_for_asr, remove_dc_offset
from ml.audio.quality import overlap_pairs, pcm16_quality
from ml.audio.asr import TranscriptSegment
from ml.audio.diarization import DiarizationSegment
from ml.audio.transcript_pipeline import align_segments
from ml.audio.asr import DeepgramTranscriber


def test_alignment_preserves_crosstalk_and_nlp_contract():
    turns = align_segments(
        [TranscriptSegment("asr-1", 0, 1000, "hello")],
        [DiarizationSegment("spk-1", 0, 800, "SPEAKER_00"), DiarizationSegment("spk-2", 500, 1000, "SPEAKER_01")],
    )
    assert turns[0].speaker == "SPEAKER_00"
    assert turns[0].overlapping_speakers == ("SPEAKER_01",)
    assert turns[0].overlap_ratio == 0.5
    assert turns[0].needs_review
    payload = turns[0].to_nlp_segment(is_final=False)
    assert payload["segment_id"] == "turn-0000"
    assert payload["is_final"] is False
    assert payload["overlaps_with_speaker_labels"] == ["SPEAKER_01"]


def test_quality_metadata_is_bounded_and_detects_silence_and_clipping():
    pcm = b"\x00\x00\xff\x7f\x00\x00\x00\x00"
    result = pcm16_quality(pcm, sample_rate_hz=1000)
    assert result.duration_ms == 4
    assert result.peak == 32767 / 32768
    assert result.silence_ratio == 0.75
    assert result.clipping_ratio == 0.25


def test_preprocessing_preserves_silence_and_removes_offset():
    silence = b"\x00\x00" * 4
    assert normalize_pcm16le(silence) == silence
    shifted = b"\x0a\x00" * 4
    assert remove_dc_offset(shifted) == silence


def test_playback_uses_half_open_intervals_and_gaps():
    first = PlaybackSegment("one", 0, 1000, "SPEAKER_00", "first")
    second = PlaybackSegment("two", 1200, 2000, "SPEAKER_01", "second")
    assert segment_at([second, first], 999) == first
    assert segment_at([second, first], 1000) is None
    assert segment_at([second, first], 1200) == second


def test_overlap_pairs_are_deterministic():
    assert overlap_pairs([
        {"segment_id": "a", "start_ms": 0, "end_ms": 100},
        {"segment_id": "b", "start_ms": 50, "end_ms": 120},
        {"segment_id": "c", "start_ms": 120, "end_ms": 200},
    ]) == [("a", "b")]


def test_preprocessing_gates_quiet_noise_but_preserves_signal():
    pcm = b"\x64\x00\x9c\xff" + b"\xb0\x04\x50\xfb"
    prepared = prepare_pcm_for_asr(pcm, noise_threshold=0.01)
    values = [int.from_bytes(prepared[index:index + 2], "little", signed=True) for index in range(0, len(prepared), 2)]
    assert values[:2] == [0, 0]
    assert max(abs(value) for value in values[2:]) > 0


def test_quality_report_exposes_review_flags():
    report = pcm16_quality(b"\xff\x7f" * 4, sample_rate_hz=1000).to_dict()
    assert "clipping" in report["quality_flags"]
    assert 0 <= report["quality_score"] <= 1


def test_deepgram_adapter_requests_diarization_and_preserves_speakers(tmp_path, monkeypatch):
    audio_path = tmp_path / "recording.webm"
    audio_path.write_bytes(b"audio")

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"results": {"utterances": [{
                "start": 0.2, "end": 1.1, "transcript": "Ship the release.",
                "confidence": 0.93, "speaker": 0,
            }]}}).encode()

    def fake_urlopen(request, timeout, context):
        assert timeout == 600
        assert context.verify_mode == 2
        assert request.data == b"audio"
        assert request.headers["Content-type"] == "audio/webm"
        assert "diarize=true" in request.full_url
        return Response()

    monkeypatch.setattr("ml.audio.asr.urlopen", fake_urlopen)
    segments = DeepgramTranscriber("test-key").transcribe(audio_path, content_type="audio/webm")

    assert len(segments) == 1
    assert segments[0].speaker_id == "SPEAKER_00"
    assert segments[0].start_ms == 200
    assert segments[0].end_ms == 1100
