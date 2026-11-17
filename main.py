from datetime import datetime, date
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import engine, Base, get_db
from models import RFQ, Bid
from auction import get_auction_status, get_ranked_bids, submit_bid

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class RFQInput(BaseModel):
    name: str
    reference_id: str
    bid_start: datetime
    bid_close: datetime
    forced_close: datetime
    pickup_date: date
    trigger_window_minutes: int
    extension_minutes: int
    trigger_type: str

class BidInput(BaseModel):
    carrier_name: str
    freight_charges: float
    origin_charges: float
    destination_charges: float
    transit_time: int
    quote_validity: date

from fastapi.responses import FileResponse

@app.get("/")
def home():
    return FileResponse("index.html")
@app.get("/details.html")
def details_page():
    return FileResponse("details.html")

@app.post("/rfqs")
def create_rfq(data: RFQInput, db: Session = Depends(get_db)):
    if data.trigger_type not in ["BID_RECEIVED", "ANY_RANK_CHANGE", "L1_CHANGE"]:
        raise HTTPException(status_code=400, detail="Invalid trigger type")
    if data.bid_close <= data.bid_start:
        raise HTTPException(status_code=400, detail="Bid close time must be after start time")
    if data.forced_close <= data.bid_close:
        raise HTTPException(status_code=400, detail="Forced close time must be after bid close time")

    if db.query(RFQ).filter(RFQ.reference_id == data.reference_id).first():
        raise HTTPException(status_code=400, detail="Reference ID already exists")

    rfq = RFQ(
        name=data.name,
        reference_id=data.reference_id,
        bid_start=data.bid_start,
        bid_close=data.bid_close,
        current_close=data.bid_close,
        forced_close=data.forced_close,
        pickup_date=data.pickup_date,
        trigger_window_minutes=data.trigger_window_minutes,
        extension_minutes=data.extension_minutes,
        trigger_type=data.trigger_type,
    )
    db.add(rfq)
    db.commit()
    db.refresh(rfq)
    return rfq

@app.get("/rfqs")
def get_all_rfqs(db: Session = Depends(get_db)):
    now = datetime.now()
    rfqs = db.query(RFQ).order_by(RFQ.id.desc()).all()
    output = []

    for r in rfqs:
        ranked = get_ranked_bids(r.bids)
        lowest = ranked[0]["bid"].total if ranked else None
        output.append({
            "id": r.id,
            "name": r.name,
            "reference_id": r.reference_id,
            "lowest_bid": lowest,
            "current_close": r.current_close,
            "forced_close": r.forced_close,
            "status": get_auction_status(r, now),
        })
    return output

@app.get("/rfqs/{rfq_id}")
def get_single_rfq(rfq_id: int, db: Session = Depends(get_db)):
    rfq = db.query(RFQ).filter(RFQ.id == rfq_id).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")

    now = datetime.now()
    ranked = get_ranked_bids(rfq.bids)
    logs = sorted(rfq.logs, key=lambda x: x.created_at, reverse=True)

    return {
        "rfq": rfq,
        "status": get_auction_status(rfq, now),
        "ranked_bids": ranked,
        "logs": logs,
    }

@app.post("/rfqs/{rfq_id}/bids")
def add_bid(rfq_id: int, data: BidInput, db: Session = Depends(get_db)):
    rfq = db.query(RFQ).filter(RFQ.id == rfq_id).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")

    bid = submit_bid(db, rfq, data)
    return {"bid": bid, "current_close": rfq.current_close}