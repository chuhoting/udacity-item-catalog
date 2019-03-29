import os
import sys
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

Base = declarative_base()

class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    email = Column(String(250), nullable=False)
    picture = Column(String(250))

    @property
    def serialize(self):

        return {
            'id' : self.id,
            'name' : self.name,
            'email': self.email,
            'picture': self.picture
        }

class SportCategory(Base):
    __tablename__ = 'sportcategory'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):

        return {
            'name' : self.name,
            'id' : self.id
        }

class SportItems(Base):
    __tablename__ = 'sportitem'

    category_id = Column(Integer, ForeignKey('sportcategory.id'))
    description = Column(String(250))
    name = Column(String(250))
    id = Column(Integer, primary_key = True)
    sportcategory = relationship(SportCategory)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):

        return{
            'name' : self.name,
            'id' : self.id,
            'description' : self.description,
            'category_id' : self.category_id
        }

engine = create_engine('sqlite:///sportcategorysportitems.db')

Base.metadata.create_all(engine)
