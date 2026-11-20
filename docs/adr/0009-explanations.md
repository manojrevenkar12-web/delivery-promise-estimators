# 0009. Roster explanations: code decides the facts, a model may only reword them

## Status

Accepted.

## Decision

- **Code decides.** `/v1/roster` returns how many drivers to ask, with facts computed in code. The factors that
  lower show probabilities come from the trees' own contributions (`pred_contribs`).
- **The template is the default.** A plain template turns the facts into two sentences.
- **A model may reword.** If an Anthropic API key is configured, Claude may reword them. Its text is used only if
  every number in it is one of the facts' numbers; otherwise the template is used.

## Consequences

A hub lead gets a reason they can check, and a model can never change the roster or invent a figure. Tests cover
three cases: an accepted rewording, a rewording with an invented number, and a timeout.
