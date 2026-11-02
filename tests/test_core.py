import unittest
from decimal import Decimal
from datetime import date
from investresearch.core import Fees, evaluate_position, apply_loss_carryforward, settle_weekdays, validate_allocation
from investresearch.analytics import indicators, pearson_aligned

class TestResearch(unittest.TestCase):
    def test_commission_floor_cap(self):
        f=Fees()
        self.assertEqual(f.order(Decimal('1000')),Decimal('5.00'))
        self.assertEqual(f.order(Decimal('10000')),Decimal('20.00'))
        self.assertEqual(f.order(Decimal('25000')),Decimal('25.00'))
    def test_round_trip_flat(self):
        x=evaluate_position(7000,0,Fees())
        self.assertEqual(x.net_pnl_before_unverified_costs_eur,Decimal('-28.00'))
    def test_positive_profit_and_ftt(self):
        x=evaluate_position(6000,0.10,Fees(),True)
        self.assertEqual(x.gross_pnl_eur,Decimal('600.00'))
        self.assertEqual(x.ftt_eur,Decimal('12.00'))
        self.assertEqual(x.buy_cost_eur,Decimal('12.00'))
        self.assertEqual(x.sell_cost_eur,Decimal('13.20'))
        self.assertEqual(x.net_pnl_before_unverified_costs_eur,Decimal('562.80'))
    def test_usd_fx_spread(self):
        x=evaluate_position(4500,0,Fees(),False,25)
        self.assertEqual(x.fx_conversion_cost_eur,Decimal('22.50'))
        self.assertEqual(x.net_pnl_before_unverified_costs_eur,Decimal('-40.50'))
    def test_capital_and_number_of_positions(self):
        validate_allocation({'A':9000,'B':7000},4000,20000,3)
        with self.assertRaises(ValueError): validate_allocation({'A':9000,'B':7000},3000,20000,3)
        with self.assertRaises(ValueError): validate_allocation({'A':2,'B':2,'C':2,'D':2},0,8,3)
    def test_loss_floor_and_cap(self):
        self.assertEqual(apply_loss_carryforward(7000,2500)['potential_tax_avoided_eur'],Decimal('650.00'))
        self.assertEqual(apply_loss_carryforward(-200,2500)['potential_tax_avoided_eur'],Decimal('0.00'))
    def test_settlement_is_only_weekday_approximation(self):
        self.assertEqual(settle_weekdays(date(2026,12,23),2,holidays=[date(2026,12,25)]),date(2026,12,28))
    def test_indicators_no_fabrication(self):
        x=indicators([100]*12)
        self.assertIsNone(x['rsi_14'])
        self.assertIsNone(x['return_20d'])
        y=indicators(list(range(101,331)))
        self.assertEqual(y['observations'],230)
        self.assertGreater(y['rsi_14'],99)
        self.assertIsNotNone(y['ma_200'])
    def test_correlation_insufficient(self):
        self.assertIsNone(pearson_aligned([.1]*5,[.2]*5))
    def test_guards(self):
        with self.assertRaises(ValueError): evaluate_position(1000,-1.2,Fees())
        with self.assertRaises(ValueError): Fees().order(0)

if __name__=='__main__':unittest.main()
