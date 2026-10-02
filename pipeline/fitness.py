"""Step and calorie estimates (kept in sync with app/app.js)."""
from . import config


def stride_m(height_cm=config.DEFAULT_HEIGHT_CM):
    return height_cm / 100 * config.STRIDE_FACTOR


def steps_for(distance_m, height_cm=config.DEFAULT_HEIGHT_CM):
    return round(distance_m / stride_m(height_cm))


def kcal_for(walk_min, queue_min=0, weight_kg=config.DEFAULT_WEIGHT_KG, brisk=False):
    met = config.MET_BRISK if brisk else config.MET_STROLL
    return round(met * weight_kg * walk_min / 60 + config.QUEUE_MET * weight_kg * queue_min / 60)
