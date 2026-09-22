# Committed experiment runs

Raw output of each experiment, one directory per experiment named
`exp-NN-<slug>/` to match its note in `thinking/experiments/`.

Committed on purpose: one example's agentic output is ~20 KB of JSON, so a
38-example three-arm experiment is around 2 MB. That is cheap enough to make
every figure in the paper re-derivable from committed data, rather than from a
run nobody can reproduce.

Not to be confused with `experiments/results/`, which is untracked working
output from experiments run on other branches.
