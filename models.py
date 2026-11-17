from datetime import datetime
from sqlalchemy import Column,Integer,Float,String, DateTime , Date,ForeignKey
from sqlalchemy.orm import relationship
from database import Base

#This table stores the rules of auction and schedule shipment request
class RFQ(Base):
    __tablename__ = "rfqs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    reference_id = Column(String, unique=True, nullable=False)
    #Starting of the bid carries can bid according to their wish
    bid_start = Column(DateTime, nullable=False)
    #closing time of the bid 
    bid_close = Column(DateTime, nullable=False)      
    current_close = Column(DateTime, nullable=False)  
    forced_close = Column(DateTime, nullable=False)
    pickup_date = Column(Date, nullable=False)
    #Extension rules 
    trigger_window_minutes = Column(Integer, nullable=False)
    #how many minutes get added   
    extension_minutes = Column(Integer, nullable=False)       
    trigger_type = Column(String, nullable=False) #BID Received ,l1 changes and any rank changes
    created_at = Column(DateTime, default=datetime.now)

    bids = relationship("Bid", back_populates="rfq")
                        
    logs = relationship("ActivityLog", back_populates="rfq")
                        

#stores the every quote submitted by carriers 
class Bid(Base):
    __tablename__ = "bids"

    id = Column(Integer, primary_key=True, index=True)
    rfq_id = Column(Integer, ForeignKey("rfqs.id"), nullable=False, index=True)
    carrier_name = Column(String, nullable=False)
    #price breakdown
    freight_charges = Column(Float, nullable=False)
    origin_charges = Column(Float, nullable=False)
    destination_charges = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    #logistic datails (used as a tie-braker if carriers bid at the same time)  
    transit_time = Column(Integer, nullable=False)  
    quote_validity = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    rfq = relationship("RFQ", back_populates="bids")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    rfq_id = Column(Integer, ForeignKey("rfqs.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)  # BID SUBMITTED, TIME EXTENDED 
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    rfq = relationship("RFQ", back_populates="logs")