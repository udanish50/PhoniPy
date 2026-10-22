"""Run with: streamlit run <installed phonipy/app.py path>."""

import io
import json
from dataclasses import asdict

import matplotlib.pyplot as plt
import pandas as pd
import soundfile as sf
import streamlit as st

from phonipy import AnalysisConfig, analyze_samples


def main():
    st.set_page_config(page_title="PhoniPy", page_icon="🎵", layout="wide")
    st.title("PhoniPy")
    st.caption("Voice stability and harmonic purity · research software")
    with st.sidebar:
        st.header("Analysis settings")
        preset = st.selectbox("Voice range / task", ["general", "low", "high", "speech", "singing"])
        reference = st.number_input("Reference note (MIDI; A4 = 69)", value=69.0)
        minimum = st.number_input("Minimum consecutive frames", min_value=1, value=8)
        periodicity = st.slider("Minimum periodicity", 0.0, 1.0, 0.65)
        config = AnalysisConfig.preset(
            preset,
            reference_key=reference,
            min_frames=int(minimum),
            min_periodicity=periodicity,
            max_duration=300.0,
        )
        st.download_button(
            "Download settings",
            json.dumps(config.to_dict(), indent=2),
            "phonipy-config.json",
            "application/json",
        )
    st.write("Upload solo voice recordings. Start with a sustained vowel or a single-note hold.")
    st.info(
        "These experimental measurements are not a diagnosis. Speech and intentional "
        "note changes can naturally produce fragmented stable-note detections."
    )
    uploads = st.file_uploader(
        "Audio files (up to 5 minutes each)",
        type=["wav", "flac", "ogg", "aiff", "mp3"],
        accept_multiple_files=True,
    )
    if not st.button("Analyze recordings", type="primary", disabled=not uploads):
        return
    rows, payloads = [], []
    progress = st.progress(0.0)
    for index, upload in enumerate(uploads):
        try:
            if upload.size > 100 * 1024 * 1024:
                raise ValueError("File exceeds the 100 MB dashboard limit")
            with sf.SoundFile(io.BytesIO(upload.getvalue())) as handle:
                if handle.frames / handle.samplerate > config.max_duration:
                    raise ValueError("Recording exceeds the five-minute dashboard limit")
                rate = handle.samplerate
                samples = handle.read(always_2d=True)
            result = analyze_samples(samples, rate, config, source=upload.name)
            rows.append({"file": upload.name, **asdict(result.metrics)})
            payloads.append(result.to_dict(include_frames=True))
            with st.expander(upload.name, expanded=len(uploads) == 1):
                st.audio(upload.getvalue())
                for warning in result.warnings:
                    st.warning(warning)
                figure = result.plot()
                st.pyplot(figure)
                plt.close(figure)
                st.dataframe(pd.DataFrame([asdict(s) for s in result.segments]))
        except (ValueError, OSError, RuntimeError) as exc:
            st.error(f"{upload.name}: {exc}")
            payloads.append({"source": upload.name, "error": str(exc)})
        progress.progress((index + 1) / len(uploads))
    if rows:
        table = pd.DataFrame(rows)
        st.subheader("Recording metrics")
        st.dataframe(table, hide_index=True)
        st.download_button(
            "Download metrics CSV", table.to_csv(index=False), "phonipy-metrics.csv", "text/csv"
        )
    st.download_button(
        "Download full results JSON",
        json.dumps(payloads, allow_nan=False),
        "phonipy-results.json",
        "application/json",
    )


if __name__ == "__main__":
    main()
