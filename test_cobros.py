"""Pruebas unitarias de la lógica independiente de cobros."""
import unittest
from decimal import Decimal
from cobros import (
    ErrorCobro, calcular_saldo_periodo, distribuir_cobro,
    aplicar_saldo_favor, resumir_operacion
)


class TestCobros(unittest.TestCase):
    def setUp(self):
        self.obligaciones = [
            {"concepto": "alquiler", "periodo_id": 10, "saldo_pendiente": "500.00", "fecha_vencimiento": "2026-10-01"},
            {"concepto": "electricidad", "periodo_id": 20, "saldo_pendiente": "120.00", "fecha_vencimiento": "2026-10-05"},
            {"concepto": "agua", "periodo_id": 30, "saldo_pendiente": "30.00", "fecha_vencimiento": "2026-10-07"},
        ]

    def test_saldo_periodo(self):
        self.assertEqual(calcular_saldo_periodo("200", ["50", "25"]), Decimal("125.00"))

    def test_pago_exacto(self):
        r = distribuir_cobro("650", self.obligaciones, "antiguedad")
        self.assertEqual(r["total_aplicado"], Decimal("650.00"))
        self.assertEqual(r["saldo_a_favor_generado"], Decimal("0.00"))

    def test_pago_parcial(self):
        r = distribuir_cobro("100", self.obligaciones, "antiguedad")
        self.assertEqual(r["total_aplicado"], Decimal("100.00"))
        self.assertEqual(r["saldo_a_favor_generado"], Decimal("0.00"))
        self.assertEqual(r["aplicaciones"][0]["concepto"], "alquiler")

    def test_excedente_es_credito(self):
        r = distribuir_cobro("800", self.obligaciones, "antiguedad")
        self.assertEqual(r["total_aplicado"], Decimal("650.00"))
        self.assertEqual(r["saldo_a_favor_generado"], Decimal("150.00"))

    def test_distribucion_manual(self):
        r = distribuir_cobro("200", self.obligaciones, "manual", [
            {"concepto": "alquiler", "periodo_id": 10, "monto": "100"},
            {"concepto": "agua", "periodo_id": 30, "monto": "30"},
        ])
        self.assertEqual(r["total_aplicado"], Decimal("130.00"))
        self.assertEqual(r["saldo_a_favor_generado"], Decimal("70.00"))

    def test_manual_no_supera_saldo_periodo(self):
        with self.assertRaises(ErrorCobro):
            distribuir_cobro("700", self.obligaciones, "manual", [
                {"concepto": "alquiler", "periodo_id": 10, "monto": "501"},
            ])

    def test_no_aplica_mas_que_recibido(self):
        with self.assertRaises(ErrorCobro):
            distribuir_cobro("50", self.obligaciones, "manual", [
                {"concepto": "alquiler", "periodo_id": 10, "monto": "60"},
            ])

    def test_credito_aplicado_a_otro_concepto_pide_confirmacion(self):
        pendiente = aplicar_saldo_favor("150", "electricidad", 20, "100")
        self.assertTrue(pendiente["requiere_confirmacion"])
        self.assertEqual(pendiente["monto_aplicado"], Decimal("0.00"))

    def test_credito_aplicado_a_otro_concepto_confirmado(self):
        r = aplicar_saldo_favor("150", "electricidad", 20, "100", confirmado=True)
        self.assertEqual(r["monto_aplicado"], Decimal("100.00"))
        self.assertEqual(r["saldo_favor_restante"], Decimal("50.00"))
        self.assertEqual(r["saldo_periodo_restante"], Decimal("0.00"))
        self.assertFalse(r["genera_ingreso"])

    def test_aplicacion_parcial_de_credito(self):
        r = aplicar_saldo_favor("150", "agua", 30, "30", "10", confirmado=True)
        self.assertEqual(r["saldo_favor_restante"], Decimal("140.00"))
        self.assertEqual(r["saldo_periodo_restante"], Decimal("20.00"))

    def test_forma_pago_unica(self):
        r = distribuir_cobro("800", self.obligaciones, "antiguedad")
        resumen = resumir_operacion("800", r, "QR")
        self.assertEqual(resumen["forma_pago"], "qr")
        with self.assertRaises(ErrorCobro):
            resumir_operacion("800", r, "efectivo + QR")

    def test_monto_cero_rechazado(self):
        with self.assertRaises(ErrorCobro):
            distribuir_cobro("0", self.obligaciones, "antiguedad")


if __name__ == "__main__":
    unittest.main(verbosity=2)
