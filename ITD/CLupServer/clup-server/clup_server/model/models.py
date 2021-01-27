from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Time, DateTime, Float, func
from werkzeug.security import generate_password_hash, check_password_hash
from config import db
import math
import datetime



class CLupUser(db.Model):
    __tablename__ = 'clupuser'

    user_id = db.Column(Integer, primary_key=True)
    name = db.Column(String(255), nullable=False)
    email = db.Column(String(255), unique=True, nullable=False)
    password = db.Column('pwd', String(255), nullable=False)
    store_op = db.Column(Boolean, nullable=False, default=False)

    tickets = db.relationship('Ticket', back_populates='user')

    def set_password(self, password : str) -> None:
        self.password = generate_password_hash(password, "sha256")

    def check_password(self, password : str) -> bool:
        return check_password_hash(self.password, password)

    @classmethod
    def find_by_email(cls, address : str):
        return cls.query.filter_by(email=address).first()
    

    def __repr__(self):
        return '<CLupUser(id=%d, name=%s, email=%s, pwd=%s, storeop=%s)>' % \
            (self.user_id, self.name, self.email, self.pwd, self.store_op)




class OpeningHours(db.Model):
    __tablename__ = 'openinghours'

    entry_id = db.Column(Integer, primary_key=True)
    store_id = db.Column(Integer,
                      ForeignKey('store.store_id',
                                 ondelete='CASCADE',
                                 onupdate='CASCADE'),
                      nullable=False)
    opening_hour = db.Column(Time, nullable=False)
    opening_weekday = db.Column(Integer, nullable=False)
    closing_hour = db.Column(Time, nullable=False)
    closing_weekday = db.Column(Integer, nullable=False)

    store = db.relationship('Store',
                         back_populates='opening_hours')


class Store(db.Model):
    __tablename__ = 'store'

    store_id = db.Column(Integer, primary_key=True)
    shop_name = db.Column(String(255), nullable=False)
    chain_name = db.Column(String(255))
    country = db.Column(String(255), nullable=False)
    city = db.Column(String(255), nullable=False)
    address = db.Column(String(255), nullable=False)
    latitude = db.Column(Float(precision=32, decimal_return_scale=None),
                      nullable=False)
    longitude = db.Column(Float(precision=32, decimal_return_scale=None),
                       nullable=False)
    total_capacity = db.Column(Integer, nullable=False)
    reserved_capacity = db.Column(Integer, nullable=False, default=0)

    tickets = db.relationship('Ticket', back_populates='store')
    opening_hours = db.relationship('OpeningHours', back_populates='store')

    def __repr__(self):
        return '<Store(id=%d, name=%s, latitude=%f, longitude=%f)>' % \
            (self.store_id, self.shop_name, self.latitude, self.longitude)

    @classmethod
    def get_all_stores_radius(cls, origin : tuple, radius : float) -> list:
        print(radius)
        return [x for x in cls.query.all() if x.gps_distance(*origin) < radius]

    def gps_distance(self, latitude : float, longitude : float) -> float:
        # Earth radius in meters
        R = 6372800
        lat1, lon1 = self.latitude, self.longitude
        lat2, lon2 = latitude, longitude

        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = math.sin(dphi/2)**2 + \
            math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        dist = 2*R*math.atan2(math.sqrt(a), math.sqrt(1 - a))
        print(dist)
        return dist




class Ticket(db.Model):
    MAX_CALL_NUMBER = 999
    EXPIRATION_INTERVAL = datetime.timedelta(seconds=4)

    STATE_ISSUED = 1
    STATE_CALLED = 2
    STATE_EXPIRED = 3
    STATE_USED = 4
    STATE_CANCELLED = 5


    __tablename__ = 'ticket'
    ticket_id = db.Column(Integer, primary_key=True)
    store_id = db.Column(Integer,
                      ForeignKey('store.store_id', ondelete='CASCADE',
                                 onupdate='CASCADE'),
                      nullable=False)
    emitted_on = db.Column(DateTime, default=func.now())
    called_on = db.Column(DateTime)
    expires_on = db.Column(DateTime, default=func.now() + EXPIRATION_INTERVAL)
    used_on = db.Column(DateTime)
    is_virtual = db.Column(Boolean, nullable=False)
    cancelled_on = db.Column(DateTime)
    user_id = db.Column(Integer,
                     ForeignKey('clupuser.user_id', ondelete='CASCADE',
                                onupdate='CASCADE'),
                     nullable=False)
    call_number = db.Column(Integer, nullable=False)

    store = db.relationship('Store',  back_populates='tickets')
    user = db.relationship('CLupUser', back_populates='tickets')

    def is_called(self):
        return self.called_on is not None
    
    def is_used(self):
        return self.used_on is not None
    
    def is_expired(self):
        return db.session.query(Ticket.expires_on <= func.now()).filter_by(ticket_id=self.ticket_id).first()[0]
    
    def is_cancelled(self):
        return self.cancelled_on is not None
    
    def state(self):
        # Define a priority network
        if self.is_cancelled():
            return Ticket.STATE_CANCELLED
        elif self.is_used():
            return Ticket.STATE_USED
        elif self.is_expired():
            return Ticket.STATE_EXPIRED
        elif self.is_called():
            return Ticket.STATE_CALLED
        else:
            return Ticket.STATE_ISSUED

    # Precondition: Store ID Exists
    @classmethod
    def get_next_call_number(cls, a_store_id : int) -> int:

        last_ticket_in_store = db.session.query(func.max(Ticket.emitted_on)).filter_by(store_id=a_store_id).subquery()
        
        value = db.session.query(Ticket.call_number).\
            filter_by(store_id=a_store_id).\
            filter(Ticket.emitted_on >= last_ticket_in_store).\
            first()
        print(f'------------------{value}')
        if value is None:
            return 1
        else:
            return (value[0] + 1) % cls.MAX_CALL_NUMBER 