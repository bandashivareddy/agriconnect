// UI estimate using the existing four-decimal quantity/price precision.
// Send quantity and price to the API; the server calculates the saved total.
export function saleTotal(quantity, price) {
  if (quantity === "" || price === "" || quantity == null || price == null) return "";
  const q = Number(quantity), p = Number(price);
  if (!Number.isFinite(q) || !Number.isFinite(p) || q < 0 || p < 0 || q >= 1e10 || p >= 1e10) return "";
  const scaled = (value) => BigInt(value.toFixed(4).replace(".", ""));
  const cents = (scaled(q) * scaled(p) + 500000n) / 1000000n;
  return `${cents / 100n}.${String(cents % 100n).padStart(2, "0")}`;
}

// Optional fields can still fail native validation when their panel is closed.
export function revealInvalidField(event) {
  let panel = event.target.closest("details");
  while (panel) { panel.open = true; panel = panel.parentElement?.closest("details"); }
}
