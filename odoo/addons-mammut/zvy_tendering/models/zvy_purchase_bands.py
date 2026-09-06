# -*- coding: utf-8 -*-
"""Purchase-level band ceilings from R-PL-012 / R-PL-013 / R-PL-014.

Amounts are inclusive (“تا”) and stored in Rials. Company scale × purchase
nature selects a row; `res.company.zvy_use_custom_bands` may override.
"""

ZVY_VALID_INQUIRY_DAYS = 30

# scale -> nature -> (minor_max, medium_max, major_max, large_ceo_max)
ZVY_PURCHASE_BANDS = {
    'small': {
        'operational': (1_000_000_000, 10_000_000_000, 20_000_000_000, 30_000_000_000),
        'non_operational': (100_000_000, 1_000_000_000, 3_000_000_000, 10_000_000_000),
    },
    'medium': {
        'operational': (3_000_000_000, 30_000_000_000, 50_000_000_000, 80_000_000_000),
        'non_operational': (300_000_000, 3_000_000_000, 10_000_000_000, 20_000_000_000),
    },
    'large': {
        'operational': (5_000_000_000, 50_000_000_000, 100_000_000_000, 200_000_000_000),
        'non_operational': (500_000_000, 5_000_000_000, 20_000_000_000, 50_000_000_000),
    },
}

ZVY_BAND_KEYS = ('minor_max', 'medium_max', 'major_max', 'large_ceo_max')


def zvy_level_from_amount(amount, ceilings):
    """Return minor/medium/major/large for an amount vs inclusive ceilings dict."""
    amount = amount or 0.0
    if amount <= ceilings['minor_max']:
        return 'minor'
    if amount <= ceilings['medium_max']:
        return 'medium'
    if amount <= ceilings['major_max']:
        return 'major'
    return 'large'
