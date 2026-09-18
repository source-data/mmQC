# Experiment analysis notebooks

One notebook per experiment, named `exp-NN-<slug>.ipynb` to match its note in
`thinking/experiments/`. The note carries hypothesis, design and findings; the
notebook carries the scoring, statistics and the figures that go into the paper.

They are separate because `.ipynb` is JSON with execution counts and embedded
outputs: it diffs badly, and a reviewer should be able to read what an experiment
claims without opening a notebook.
