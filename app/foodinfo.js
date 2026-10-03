/* Eatery facts the list and the place page share: diet groups and a cost-for-two estimate. */

// Egg dishes Kolkata menus actually say: egg roll, dimer devil, anda, mughlai paratha (egg-stuffed), omelette.
const EGG = /\begg|\bdim(er)?\b|\bdeem|\banda\b|omelet|omlette|mughlai|moglai|dimer/i;
export const hasEgg = (f) => f.veg !== 'veg' && (f.egg === true || EGG.test(f.dishes.join(' ')));

/** Diet chips: Veg = pure-veg kitchens, Non-veg = serves meat or fish, Egg = has egg dishes. Several chips = any of them. */
export const DIETS = ['veg', 'nonveg', 'egg'];
export function dietMatch(f, chosen) {
  const want = DIETS.filter((d) => chosen.has(d));
  if (!want.length) return true;
  return want.some((d) => (d === 'veg' ? f.veg === 'veg' : d === 'nonveg' ? f.veg !== 'veg' : hasEgg(f)));
}

// Typical bill for two (₹), by kind of place and its price tier (1 = cheap, 3 = pricey). Rounded, festival-time menus.
const FOR_TWO = {
  street: [150, 250, 400], sweets: [150, 300, 500], drinks: [120, 250, 400],
  cabin: [300, 500, 800], restaurant: [500, 1000, 1800],
};
/** ≈₹ for two: the CSV's cost2 when someone checked it, else the estimate above. */
export const cost2 = (f) => f.cost2 || (FOR_TWO[f.type] || FOR_TWO.restaurant)[Math.min(Math.max(f.price, 1), 3) - 1];
export const rupees = (n) => '₹' + n.toLocaleString('en-IN');
