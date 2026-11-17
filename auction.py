from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models import RFQ, Bid, ActivityLog

def get_auction_status(rfq,now):
    if now >= rfq.forced_close:
        return "Force Closed" if rfq.current_close > rfq.bid_close else "Closed"
    if now >= rfq.current_close:
        return "Force Closed" if rfq.current_close >= rfq.forced_close else "Closed"
    return "Active"

def get_ranked_bids(bids):
    
    best_by_carrier = {}
    for bid in bids:
        existing = best_by_carrier.get(bid.carrier_name)
        if existing is None or (bid.total, bid.created_at) < (existing.total, existing.created_at):
            best_by_carrier[bid.carrier_name] = bid

    sorted_bids = sorted(best_by_carrier.values(), key=lambda b: (b.total, b.created_at))

    ranked = []
    for idx, bid in enumerate(sorted_bids, start=1):
        ranked.append({
            "rank": f"L{idx}",
            "bid": bid
        })
    return ranked


def submit_bid(db: Session, rfq: RFQ, bid_data, now = None):
    now = now or datetime.now()

    
    if now < rfq.bid_start:
        raise HTTPException(status_code=400, detail="Auction has not started yet")
    if now >= rfq.current_close or now >= rfq.forced_close:
        raise HTTPException(status_code=400, detail="Auction is already closed")

    
    old_ranked = get_ranked_bids(rfq.bids)
    old_order = [item["bid"].carrier_name for item in old_ranked]

    
    total_price = bid_data.freight_charges + bid_data.origin_charges + bid_data.destination_charges
    new_bid = Bid(
        rfq_id=rfq.id,
        carrier_name=bid_data.carrier_name,
        freight_charges=bid_data.freight_charges,
        origin_charges=bid_data.origin_charges,
        destination_charges=bid_data.destination_charges,
        total=total_price,
        transit_time=bid_data.transit_time,
        quote_validity=bid_data.quote_validity,
        created_at=now
    )
    db.add(new_bid)
    db.flush()

    db.add(ActivityLog(
        rfq_id=rfq.id,
        event_type="BID_SUBMITTED",
        message=f"Bid submitted by {new_bid.carrier_name} for {total_price}",
        created_at=now
    ))

    
    all_bids = rfq.bids + [new_bid] if new_bid not in rfq.bids else rfq.bids
    new_ranked = get_ranked_bids(all_bids)
    new_order = [item["bid"].carrier_name for item in new_ranked]

    
    window_start = rfq.current_close - timedelta(minutes=rfq.trigger_window_minutes)
    if now >= window_start:
        should_extend = False

        if rfq.trigger_type == "BID_RECEIVED":
            should_extend = True
        elif rfq.trigger_type == "ANY_RANK_CHANGE":
            should_extend = (old_order != new_order)
        elif rfq.trigger_type == "L1_CHANGE":
            old_l1 = old_order[0] if old_order else None
            new_l1 = new_order[0] if new_order else None
            should_extend = (new_l1 is not None and old_l1 != new_l1)

        
        if should_extend and rfq.current_close < rfq.forced_close:
            old_close = rfq.current_close
            proposed_close = rfq.current_close + timedelta(minutes=rfq.extension_minutes)
            rfq.current_close = min(proposed_close, rfq.forced_close)

            db.add(ActivityLog(
                rfq_id=rfq.id,
                event_type="TIME_EXTENDED",
                message=f"Close time extended from {old_close.strftime('%H:%M')} to {rfq.current_close.strftime('%H:%M')} due to {rfq.trigger_type}",
                created_at=now
            ))

    db.commit()
    db.refresh(new_bid)
    return new_bid