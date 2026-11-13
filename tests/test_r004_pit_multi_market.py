"""R-004 multi-market historical PIT intake, ONLY FICTIONAL inputs.

All identities, original documents and snapshots in these tests are synthetic.
No price feed is queried or inferred and no real-market sample is certified.
"""
from __future__ import annotations

import csv
from datetime import date,timedelta
import hashlib
import io
import json

import pytest

from investresearch.quality import valid_isin
from investresearch.research_cli import main
from investresearch.research_historical_validation_v2 import preregistered_anchors
from investresearch.research_historical_validation_v3 import v3_protocol
from investresearch.research_pit_multi_market import (
    SCHEMA, _draw, pilot_pit_multi_market, read_historical_pack,
    write_private_pit_audit,
)

SEED="1234567890abcdef"*4
AREA_VENUE={"USA":"XNYS","ITALY":"XMIL","GERMANY":"XETR","FRANCE":"XPAR"}
AREA_PREFIX={"USA":"US","ITALY":"IT","GERMANY":"DE","FRANCE":"FR"}


def isin_for(market,n):
    base=AREA_PREFIX[market]+f"{n:09d}"
    return next(base+str(k) for k in range(10) if valid_isin(base+str(k)))


def anchors():
    return preregistered_anchors(["XNYS","XNAS","XMIL","XPAR","XETR"],v3_protocol()[0])


def fixture(tmp_path, *, missing=None, rights_override=None, count=10,
            additional_future_snapshot=False):
    private=tmp_path/"data/private"
    private.mkdir(parents=True)
    first=anchors()[0]
    specs=[]
    def add_snap(market, day, prefix):
        source=private/f"{market}_{prefix}_FICTIONAL_DOCUMENT.txt"
        source.write_text(f"FICTIONAL archived member-document, {market} {day}")
        transcription=private/f"{market}_{prefix}_FICTIONAL_TRANSCRIPTION.csv"
        out=io.StringIO(newline="")
        writer=csv.writer(out,lineterminator="\n")
        writer.writerow(("security_key","isin","venue","sector","asset_type",
                         "oil_exposure","listing_date"))
        for j in range(count):
            writer.writerow((f"FICT_{market}_{j:03d}",isin_for(market,j+1),
                             AREA_VENUE[market],f"SECTOR_{j%4}",
                             "EQUITY","none","2020-01-02"))
        transcription.write_text(out.getvalue())
        def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
        specs.append({
            "market":market,"snapshot_as_of":day,
            "original_published_on":(date.fromisoformat(day)-timedelta(days=2)).isoformat(),
            "source_kind":"ARCHIVED_HISTORICAL_SNAPSHOT_OPERATOR_TRANSCRIBED",
            "usage_rights":"UNVERIFIED" if rights_override==market else
                           "OPERATOR_REVIEWED_PERSONAL_NONCOMMERCIAL",
            "source_url":"https://example.org/FICTIONAL-NOT-OFFICIAL",
            "original_path":str(source),"original_sha256":sha(source),
            "transcription_path":str(transcription),
            "transcription_sha256":sha(transcription),
        })
    for m in AREA_VENUE:
        if m!=missing:
            add_snap(m,first,"FIRST")
            if additional_future_snapshot:
                add_snap(m,anchors()[1],"SECOND")
    pack=private/"ORIGINAL_FICTIONAL_PACK.json"
    pack.write_text(json.dumps({"schema_version":SCHEMA,"snapshots":specs}))
    return private,pack


def run(private,pack,**kwargs):
    return pilot_pit_multi_market(pack,private_root=private,seed=SEED,**kwargs)


def test_deterministic_32_name_first_anchor_with_four_markets(tmp_path):
    private,pack=fixture(tmp_path)
    a=run(private,pack,first_anchors=1)
    b=run(private,pack,first_anchors=1)
    assert a==b
    assert a["pilot_anchors"]==1
    assert a["target_securities_per_anchor"]==32
    assert a["drawn_complete_unverified_anchors"]==1
    entry=a["anchor_audit"][0]
    assert entry["picked"]==32
    assert entry["status"]=="PILOT_COHORT_DRAWN_UNVERIFIED"
    assert len({x["isin"] for r in entry["market"].values()
               for x in r["selected"]})==32
    for area in AREA_VENUE:
        assert entry["market"][area]["count"]==8
        assert len({x["sector"] for x in entry["market"][area]["selected"]})>=3
    assert a["historical_membership_independently_authenticated"] is False
    assert a["prices_or_corporate_actions_acquired"] is False
    assert a["research_ready"] is False
    assert a["trade_ready"] is False


def test_later_snapshots_cannot_change_earlier_date_selections(tmp_path):
    p1,pack1=fixture(tmp_path/"one")
    p2,pack2=fixture(tmp_path/"two",additional_future_snapshot=True)
    old=run(p1,pack1,first_anchors=1)["anchor_audit"][0]
    after=run(p2,pack2,first_anchors=2)["anchor_audit"]
    assert after[0]["anchor"]==old["anchor"]
    for market in AREA_VENUE:
        assert after[0]["market"][market]["selected"]==old["market"][market]["selected"]
        assert after[1]["market"][market]["snapshot_as_of"]==anchors()[1]


def test_missing_country_stale_or_unlicensed_snapshot_blocks_and_never_backfills(tmp_path):
    for scenario in ("MISSING","RIGHTS","STALE"):
        private,pack=fixture(tmp_path/scenario,
                             missing="FRANCE" if scenario=="MISSING" else None,
                             rights_override="FRANCE" if scenario=="RIGHTS" else None)
        report=run(private,pack,first_anchors=4 if scenario=="STALE" else 1)
        if scenario=="STALE":
            assert report["anchor_audit"][-1]["market"]["FRANCE"]["status"]=="BLOCKED_STALE_HISTORICAL_MEMBERSHIP"
        else:
            assert report["anchor_audit"][0]["market"]["FRANCE"]["status"]==(
                "BLOCKED_NO_HISTORICAL_MEMBERSHIP" if scenario=="MISSING"
                else "BLOCKED_SOURCE_USAGE_RIGHTS")
        assert report["drawn_complete_unverified_anchors"]==(
            3 if scenario=="STALE" else 0)
        assert report["trade_ready"] is False


def test_original_snapshot_hash_tampering_is_rejected(tmp_path):
    private,pack=fixture(tmp_path)
    doc=json.loads(pack.read_text())
    path=private/"ITALY_FIRST_FICTIONAL_TRANSCRIPTION.csv"
    path.write_bytes(path.read_bytes()+b"FICT_UNKNOWN\n")
    with pytest.raises(ValueError,match="SHA-256 mismatch"):
        run(private,pack)
    assert not (private/"PILOT_AUDIT.json").exists()


@pytest.mark.parametrize("field,value",[
    ("original_published_on","2026-12-01"),
    ("usage_rights","UNKNOWN_STATE"),
    ("source_url","http://insecure.example.org"),
    ("snapshot_as_of","not-a-date"),
    ("source_kind","PROVIDER_DATA_UNVERIFIED"),
])
def test_bad_original_membership_snapshot_evidence_rejected(tmp_path,field,value):
    private,pack=fixture(tmp_path)
    doc=json.loads(pack.read_text())
    doc["snapshots"][0][field]=value
    pack.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        run(private,pack)


def test_bad_duplicate_security_and_future_listing_rejected(tmp_path):
    private,pack=fixture(tmp_path)
    doc=json.loads(pack.read_text())
    src=private/"USA_FIRST_FICTIONAL_TRANSCRIPTION.csv"
    blob=src.read_bytes()
    source=doc["snapshots"][0]
    assert source["market"]=="USA"
    # A second identical original listing cannot count twice.
    src.write_bytes(blob+blob.splitlines()[1]+b"\n")
    source["transcription_sha256"]=hashlib.sha256(src.read_bytes()).hexdigest()
    pack.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match="Duplicate"):
        run(private,pack)
    # A future listing date is never backfilled into the 2021 sample.
    src.write_bytes(blob.replace(b"2020-01-02",b"2026-12-01",1))
    source["transcription_sha256"]=hashlib.sha256(src.read_bytes()).hexdigest()
    pack.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match="future"):
        run(private,pack)


def test_draw_is_independent_of_source_csv_row_order():
    rows=[{"security_key":f"FICT_{j:03d}","sector":f"S{j%4}",
           "listing_date":"2020-01-01","oil_exposure":"none"}
          for j in range(15)]
    a,diag=_draw(rows,"2021-07-01","ITALY",SEED,quota=8,cap_per_sector=3)
    b,_=_draw(list(reversed(rows)),"2021-07-01","ITALY",SEED,
              quota=8,cap_per_sector=3)
    assert [x["security_key"] for x in a]==[x["security_key"] for x in b]
    assert diag["picked"]==8


def test_private_writer_and_cli_never_write_public_price_or_overwrite(tmp_path,capsys):
    private,pack=fixture(tmp_path)
    rep=run(private,pack,first_anchors=1)
    out=private/"PILOT_AUDIT.json"
    write_private_pit_audit(rep,out,private_root=private)
    assert json.loads(out.read_text())["trade_ready"] is False
    with pytest.raises(ValueError,match="NEW"):
        write_private_pit_audit(rep,out,private_root=private)
    with pytest.raises(ValueError):
        write_private_pit_audit(rep,tmp_path/"public.json",private_root=private)
    cli_out=private/"PILOT_FROM_CLI.json"
    main(["pit-multi-market-pilot","--pack",str(pack),"--private-root",
          str(private),"--seed",SEED,"--first-anchors","1","--output",str(cli_out)])
    assert json.loads(cli_out.read_text())==rep
    assert "NOT PIT-certified" in capsys.readouterr().out
    assert "original_prices" not in cli_out.read_text()
