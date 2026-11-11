"""Adversarial V3 spread, crash, suspension, multiple venue and quantile tests.

No prices in these tests come from a market provider. This intentionally
does NOT change the frozen V1/V2/V3 decision gate.
"""
from datetime import date, timedelta
from decimal import Decimal
from statistics import mean

import pytest

from investresearch.historical_calendar_v2 import dates_v2
from investresearch.research_historical_validation import _net_trade, _ci
from investresearch.research_historical_validation_v2 import _forward
from investresearch.research_historical_validation_v3 import (
    _planned_exit, v3_protocol,
)
from investresearch.research_slippage_v3 import (
    net_at_bps, fold_spread_scenarios, aggregate_spread_scenarios,
)
from investresearch.research_outcome_diagnostics_v3 import (
    unresolved_reason, stale_close_warning, REASONS,
)


@pytest.mark.parametrize("currency",["EUR","USD"])
@pytest.mark.parametrize("notional", [5000.,10000.,250.])
@pytest.mark.parametrize("ratio",[.8,1.,1.15,1.75])
def test_frozen_zero_spread_reconciles_legacy_trade_math(currency,notional,ratio):
    policy,_=v3_protocol()
    cost=policy["costs"]
    path=[
        ("2024-01-03",Decimal("100"),Decimal("100000")),
        ("2024-02-15",Decimal(str(100*ratio)),Decimal("100000")),
    ]
    baseline,_,gross=_net_trade(path,notional=notional,
        fee_bps=cost["commission_fraction_each_side"],
        min_fee=cost["minimum_commission_eur_each_side"],
        fx_bps=cost["usd_fx_fraction_each_side"],usd=currency=="USD")
    assert abs(net_at_bps(gross,currency,cost,notional,0)-baseline)<1.e-12


@pytest.mark.parametrize("currency",["EUR","USD"])
def test_spread_per_side_is_monotonic_and_no_favorable_execution(currency):
    c=v3_protocol()[0]["costs"]
    for gross in (-.1,0,.1,.8):
        observed=[net_at_bps(gross,currency,c,5000.,bps)
                  for bps in (0,10,25,50)]
        assert observed==sorted(observed,reverse=True)
        assert observed[-1]<observed[0]
        assert all(x>-1. for x in observed)


def test_same_k_spread_reuses_exact_original_members_and_costs():
    p=v3_protocol()[0]
    ranked=[
        {"id":"FAKE_A","currency":"EUR"},
        {"id":"FAKE_B","currency":"USD"},
        {"id":"FAKE_C","currency":"EUR"},
        {"id":"FAKE_D","currency":"USD"},
    ]
    observed={
        "FAKE_A":{"gross":.08},
        "FAKE_B":{"gross":-.06},
        "FAKE_C":{"gross":.14},
        "FAKE_D":{"gross":-.11},
    }
    scenarios=fold_spread_scenarios(ranked,observed,ranked[:2],ranked[-2:],p)
    assert [s["bps_each_side"] for s in scenarios]==[0,10,25,50]
    for s in scenarios:
        vals=[net_at_bps(observed[x["id"]]["gross"],x["currency"],p["costs"],5000.,
                         s["bps_each_side"]) for x in ranked]
        assert abs(s["selected_net"]-mean(vals[:2]))<1.e-8
        assert abs(s["same_K_random_expected_net"]-mean(vals))<1.e-8
        assert abs(s["same_K_excess_net"]-(mean(vals[:2])-mean(vals)))<1.e-8
    agg=aggregate_spread_scenarios(
        [{"slippage_spread_scenarios_DESCRIPTIVE_ONLY":scenarios}], [0,10,25,50])
    assert len(agg)==4
    assert abs(agg[0]["mean_same_K_excess_net_DESCRIPTIVE_ONLY"]-
               scenarios[0]["same_K_excess_net"])<1e-12
    with pytest.raises(ValueError):
        fold_spread_scenarios(ranked,{"FAKE_A":{"gross":.08}},
                              ranked[:2],ranked[-2:],p)


@pytest.mark.parametrize("invalid", [-1,1,100,"10",float("nan")])
def test_spread_cannot_create_unregistered_or_nonfinite_scenario(invalid):
    c=v3_protocol()[0]["costs"]
    with pytest.raises(ValueError):
        net_at_bps(.03,"EUR",c,5000.,invalid)


def fictional_future(*,jump=None,stale_days=0,drop_middle=False,venue="XMIL"):
    sessions=dates_v2(date(2024,1,3),date(2024,5,31),venue)[:32]
    rows=[]
    for i,s in enumerate(sessions):
        price=Decimal("100") + Decimal(i)/Decimal(100)
        if stale_days and 2<=i<stale_days+2:
            price=Decimal("100.01")
        if jump is not None:
            price=Decimal("100") if i<jump else Decimal("84")
        rows.append((s,price,Decimal("100000")))
    if drop_middle:
        rows.pop(12)
    return rows


def test_ge15_percent_crash_is_not_misreported_as_certified_split_or_payout():
    p=v3_protocol()[0]
    c={"id":"FICTIONAL_CRASH","venue":"XMIL","currency":"EUR"}
    rows=fictional_future(jump=6)
    assert _forward(c,rows,"2024-01-02",p,5000.) is None
    reason=unresolved_reason(c,rows,"2024-01-02",30)
    assert reason=="JUMP_GE15_PERCENT_CORPORATE_ACTION_OR_REAL_CRASH_UNRESOLVED"
    assert reason in REASONS
    # Must NOT invent settlement or treat this as -100%, and no posthoc replacement.


def test_flat_closes_warn_about_possible_halt_without_fabricated_halt_status():
    p=v3_protocol()[0]
    c={"id":"FICTIONAL_HALTED_OR_ROUNDED","venue":"XMIL","currency":"EUR"}
    data=fictional_future(stale_days=8)
    # Frozen V3 still prices the path; stale status alone is not a dated
    # exchange halt announcement or an independently adjusted source.
    outcome=_forward(c,data,"2024-01-02",p,5000.)
    assert outcome is not None
    assert stale_close_warning(c,data,"2024-01-02",30) is True
    normal=fictional_future()
    assert stale_close_warning(c,normal,"2024-01-02",30) is False


def test_missing_middle_exchange_session_is_unresolved_not_silently_shortened():
    p=v3_protocol()[0]
    c={"id":"FICTIONAL_DATA_OUTAGE","venue":"XMIL","currency":"EUR"}
    rows=fictional_future(drop_middle=True)
    assert _forward(c,rows,"2024-01-02",p,5000.) is None
    assert unresolved_reason(c,rows,"2024-01-02",30)==(
        "MISSING_OR_DISCONTINUOUS_EXCHANGE_SESSION")


def test_mixed_venues_planned_exit_uses_latest_actual_market_close():
    p=v3_protocol()[0]
    venues=["XNAS","XMIL","XETR","XPAR"]
    t="2024-03-28"
    start=date.fromisoformat(t)+timedelta(days=1)
    exits={v:dates_v2(start,date(2026,12,31),v)[30] for v in venues}
    actual=_planned_exit(t,venues,p)
    assert actual==max(exits.values())
    assert actual==_planned_exit(t,list(reversed(venues)),p)
    assert all(actual>=last for last in exits.values())
    assert len(set(exits.values()))>=2


def test_frozen_percentile_floor_is_documented_not_silently_revised():
    # This is the historical V3 percentile convention: do not retrofit a
    # different estimator to protocol V3; evaluate sensitivity as successor.
    assert _ci(list(range(101)))==[2,97]
