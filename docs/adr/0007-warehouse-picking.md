# 0007. Picking: routes over the picks, savings batching, busiest SKUs near pack-out

## Status

Accepted, as the starting point for Warehouse Optimization.

## Decision

- **Routing.** A tour over the pick locations themselves, on true walking distances (nearest neighbour, then
  2-opt), instead of S-shape or return routing.
- **Batching.** Seed and savings: start from the oldest order, then add the order that adds the least walking,
  within the cart's 12 crates.
- **Slotting.** One re-slot from four weeks of order lines: the busiest SKUs go to the slots nearest pack-out.

## Consequences

- **What each piece is worth.** Each is measured alone by ablation, and slotting and routing carry most of the
  gain.
- **Re-slotting costs labour once.** The cost is stated in `config/options.yaml`.
- **Not modelled:** congestion in aisles, picker skill, and crates too heavy for a cart shelf.
