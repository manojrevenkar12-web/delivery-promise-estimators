/**
 * One orchestrated moment: on first load the promise bars fill from the left, one row after another. After that,
 * motion only answers an action (switching the day's metric redraws its lines).
 */
export const motionTokens = { quick: 0.16, fill: 0.9, stagger: 0.12, draw: 0.6, ease: [0.2, 0.7, 0.2, 1] as const } as const;
