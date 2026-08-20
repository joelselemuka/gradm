from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import ProductBarcode, ProductVariant

_EAN_L = {
    "0": "0001101", "1": "0011001", "2": "0010011", "3": "0111101", "4": "0100011",
    "5": "0110001", "6": "0101111", "7": "0111011", "8": "0110111", "9": "0001011",
}
_EAN_G = {
    "0": "0100111", "1": "0110011", "2": "0011011", "3": "0100001", "4": "0011101",
    "5": "0111001", "6": "0000101", "7": "0010001", "8": "0001001", "9": "0010111",
}
_EAN_R = {
    "0": "1110010", "1": "1100110", "2": "1101100", "3": "1000010", "4": "1011100",
    "5": "1001110", "6": "1010000", "7": "1000100", "8": "1001000", "9": "1110100",
}
_EAN_PARITY = {"0": "LLLLLL", "1": "LLGLGG", "2": "LLGGLG", "3": "LLGGGL", "4": "LGLLGG", "5": "LGGLLG", "6": "LGGGLL", "7": "LGLGLG", "8": "LGLGGL", "9": "LGGLGL"}


def barcode_svg(code: str, width: int = 300, height: int = 110) -> str:
    """Render a standards-compliant EAN-13 barcode as inline SVG."""
    code = str(code or "")
    if len(code) != 13 or not code.isdigit() or ean13_checksum(code[:12]) != code[-1]:
        return ""
    pattern = "101"
    parity = _EAN_PARITY[code[0]]
    for digit, side in zip(code[1:7], parity):
        pattern += (_EAN_L if side == "L" else _EAN_G)[digit]
    pattern += "01010"
    for digit in code[7:]:
        pattern += _EAN_R[digit]
    pattern += "101"
    bar_width = width / len(pattern)
    bars = "".join(f'<rect x="{index * bar_width:.3f}" y="0" width="{bar_width + .08:.3f}" height="82"/>' for index, bit in enumerate(pattern) if bit == "1")
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Code-barres {code}"><rect width="100%" height="100%" fill="white"/>{bars}<text x="{width / 2:.1f}" y="103" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" letter-spacing="2">{code}</text></svg>'


def ean13_checksum(body: str) -> str:
    """Return the EAN-13 check digit for a 12 digit body."""
    if len(body) != 12 or not body.isdigit():
        raise ValidationError("Le corps du code interne doit contenir 12 chiffres.")
    total = sum(int(value) * (3 if index % 2 else 1) for index, value in enumerate(body))
    return str((10 - (total % 10)) % 10)


class ProductBarcodeService:
    @staticmethod
    def add_alias(variant: ProductVariant, code: str, kind: str, actor=None, source: str = ""):
        code = (code or "").strip()
        if not code:
            raise ValidationError("Le code-barres est obligatoire.")
        with transaction.atomic():
            existing = ProductBarcode.objects.select_for_update().filter(code=code).first()
            if existing:
                if existing.variant_id != variant.pk:
                    raise ValidationError("Ce code-barres est déjà associé à un autre article.")
                if not existing.active:
                    existing.active = True
                    existing.deactivated_at = None
                    existing.kind = kind
                    existing.source = source
                    existing.save(update_fields=["active", "deactivated_at", "kind", "source"])
                return existing
            try:
                return ProductBarcode.objects.create(
                    variant=variant,
                    code=code,
                    kind=kind,
                    source=source,
                    created_by=actor,
                )
            except IntegrityError as exc:
                raise ValidationError("Ce code-barres existe déjà.") from exc

    @staticmethod
    def ensure_internal_code(variant: ProductVariant, actor=None):
        existing = variant.barcode_aliases.filter(kind=ProductBarcode.Kind.INTERNAL, active=True).first()
        if existing:
            return existing
        # Prefix 20 identifies an internal EAN-13; the variant id keeps it stable.
        body = f"20{variant.pk:010d}"[-12:]
        code = f"{body}{ean13_checksum(body)}"
        try:
            alias = ProductBarcodeService.add_alias(variant, code, ProductBarcode.Kind.INTERNAL, actor=actor, source="Génération automatique")
        except ValidationError:
            # This is only possible after an import collision; retry with a timestamp-derived body.
            body = (f"29{timezone.now().strftime('%y%m%d%H%M')}")[-12:]
            code = f"{body}{ean13_checksum(body)}"
            alias = ProductBarcodeService.add_alias(variant, code, ProductBarcode.Kind.INTERNAL, actor=actor, source="Génération automatique")
        if not variant.store_barcode:
            ProductVariant.objects.filter(pk=variant.pk).update(store_barcode=alias.code)
            variant.store_barcode = alias.code
        return alias

    @staticmethod
    def generate_internal_code(variant: ProductVariant, actor=None):
        """Always create a new internal barcode for the same product variant."""
        sequence = variant.barcode_aliases.filter(kind=ProductBarcode.Kind.INTERNAL).count() + 1
        while True:
            body = f"20{variant.pk % 10000000:07d}{sequence % 1000:03d}"
            code = f"{body}{ean13_checksum(body)}"
            if not ProductBarcode.objects.filter(code=code).exists():
                return ProductBarcodeService.add_alias(variant, code, ProductBarcode.Kind.INTERNAL, actor=actor, source="Génération interne")
            sequence += 1

    @staticmethod
    def deactivate_alias(alias: ProductBarcode):
        alias.active = False
        alias.deactivated_at = timezone.now()
        alias.save(update_fields=["active", "deactivated_at"])
