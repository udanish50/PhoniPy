"""The manuscript's composite harmonic-purity / stable-note plot."""


def composite_plot(result, path=None):
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except ImportError as exc:
        raise ImportError("Install phonipy[plot] to generate composite plots") from exc
    figure = Figure(figsize=(12, 4), layout="constrained")
    FigureCanvasAgg(figure)
    axis = figure.subplots()
    axis.plot(
        [f.start for f in result.frames],
        [f.energy_ratio for f in result.frames],
        color="0.45",
        linewidth=0.8,
        label="Harmonic energy ratio",
    )
    for segment in result.segments:
        axis.axvspan(segment.start, segment.end, alpha=0.1, color="blue")
        axis.scatter([segment.start], [segment.mean_energy], color="blue", s=20)
        axis.annotate(
            str(segment.key),
            (segment.start, segment.mean_energy),
            xytext=(2, 8),
            textcoords="offset points",
            fontsize=8,
            color="blue",
        )
        axis.scatter([segment.end], [segment.mean_energy], color="red", s=20)
        axis.annotate(
            f"{segment.frame_count} frames",
            (segment.end, segment.mean_energy),
            xytext=(2, -14),
            textcoords="offset points",
            fontsize=7,
            color="red",
        )
    axis.set(
        xlabel="Time (seconds)",
        ylabel="Harmonic-series / total energy",
        ylim=(0, 1.1),
        xlim=(0, max(result.metrics.raw_duration, 0.01)),
        title="PhoniPy — stable notes (MIDI numbering) and harmonic purity",
    )
    axis.legend(loc="lower right")
    if path:
        figure.savefig(path, dpi=160)
    return figure
