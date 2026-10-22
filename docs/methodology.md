# Operational specification: nsdf-harmonic-v2

This specification defines PhoniPy's deterministic detector, including the windowing and
pitch-estimation choices left open by the measurement framework. All ten summary equations
follow Appendix A of the methodology manuscript. Clinical validation remains separate.

## Preprocessing

Decode PCM as float64; preserve amplitude units; select the highest whole-recording RMS
channel by default; polyphase-resample to 16 kHz. Do not denoise or normalize automatically.
Subtract each frame's mean. The RMS gate uses the mean-centered unwindowed frame.

## Fundamental candidate

For each window of N samples, compute autocorrelation R(k) by zero-padded FFT. For
lags within the pitch range, compute the normalized square difference function:

`NSDF(k) = 2 R(k) / (sum(x[:N-k]^2) + sum(x[k:]^2))`.

Find local maxima; retain peaks at least 0.65 and at least 90% of the highest local maximum.
Select the earliest retained lag and interpolate its NSDF maximum parabolically (±0.5 sample).
Frequency is sample rate divided by interpolated lag. This periodicity-based candidate
selection is followed by explicit harmonic-series energy measurement. It can handle a missing
fundamental when the remaining harmonics imply its period, but octave errors remain possible.

## Harmonic ratio

Apply a symmetric Hann window and compute a real FFT with length `2**ceil(log2(4*N))`.
Square magnitudes; double interior bins for one-sided power. The denominator is all spectral
power, including DC residual. For each harmonic h=1..12 below Nyquist, integrate bins within
`half_width = min(max(22 Hz, 1.5 * sample_rate/N), 0.35*f0)` of h*f0.
Use the union of bins, never sum overlapping bands twice. Divide this energy by total power.
Zero padding interpolates the spectrum; it does not improve physical resolution.

Spectral flatness is the geometric-to-arithmetic power mean for bins from fmin to Nyquist.
Accept frames only if RMS >= -60 dBFS, periodicity >= 0.65, harmonic ratio >= 0.15,
flatness <= 0.6, and refined f0 lies inside the configured range.
These are engineering defaults, not clinically optimized cutoffs.

## Note and time conventions

`fractional_key = 69 + 12*log2(f0/440)`; rounded key is `floor(fractional_key + 0.5)`.
Indices refer to individual notes, never major/minor tonal keys. A same-key run must have
eight accepted consecutive frames; invalid frames or a different key end the run. Do not
merge gaps. Backdate onset to the run's first frame; close at the end of its last hop.
Forward-looking spectral windows may include the next event: boundary timing is therefore
approximate at window scale. The eight-frame rule corresponds to hop occupancy, not eight
independent spectra. The final truncated hop can make a final eight-frame run shorter than
138 ms; min_frames is a count criterion, not an independent duration criterion.

Frame intervals are disjoint `[start, min(start+hop, raw_duration))`. Compute segment energy
and fractional pitch with these interval lengths as weights. Average offset is an unweighted
mean of segment mean fractional pitches minus the user reference. Average energy is weighted
by segment duration (equivalently by frame occupancy over valid intervals).

With no detections, return zero extent/count metrics and null means; no pitch/energy observations
exist from which to infer those means. Preserve a no-detections warning. Breakouts counts all
segments, not just reacquisitions. Continuity is exactly reciprocal segment count for N>0.

## Interpretation

Hoarseness is a residual-energy label specified by the manuscript; microphone noise, harmonic
bandwidth, formants, and the finite harmonic count all influence it. It is not the same as HNR,
CPP, or perceptual hoarseness, and values near 0.9 for clean voice are not guaranteed.
Rounded-note persistence misses within-note variation and can fragment vibrato near a semitone
boundary. A stable wrong note can have excellent purity/continuity; examine offset separately.
Settings and task length must be fixed before comparing recordings. No universal healthy/abnormal
thresholds or Parkinson's classification are supplied.

Jitter, shimmer, CPP, HNR, and AVQI are outside this ten-metric specification and are not
substituted for the defined measurements.


## Browser and Python implementations

Version 0.2.0 uses the same radix-two FFT size in both runtimes. Numeric conformance tests
compare metrics and frame detections on identical Float32 PCM inputs. Browser decoding and
resampling use Web Audio; Python uses libsndfile and SciPy polyphase resampling. Decoder
and resampler differences can affect samples near acceptance/rounding thresholds.

The web application processes recordings in a browser worker. Audio, waveform previews,
and measurements are held only in transient memory; no results, recording names, or audio
are sent to an analysis server or written to browser storage. Clearing or closing the
workspace releases its references and revokes playback object URLs. Download actions create
user-requested local files; there is no automatic export or saved history.
