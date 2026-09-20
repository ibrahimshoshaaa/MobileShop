from dataclasses import replace
from decimal import Decimal
from shared.models.foundation import Settings

class SettingsService:
    def validate(self, settings: Settings) -> Settings:
        rate = Decimal(str(settings.default_transfer_commission_rate))
        if rate < 0 or rate > 1:
            raise ValueError("INVALID_INPUT")
        if settings.currency != "EGP":
            # EGP is primary; other currencies can be supported later only if explicitly specified.
            raise ValueError("INVALID_CURRENCY")
        return settings
