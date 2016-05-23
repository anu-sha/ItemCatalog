import os
import sys

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

Base=declarative_base()

#User class for maintaining users data 
class User(Base):
    __tablename__='user'
    id=Column(Integer, primary_key=True)
    name=Column(String(250), nullable=False)
    picture=Column(String(250), nullable=False)
    email=Column(String(250))

#Category class ->table to hold category information
class Category(Base):
    __tablename__='category'
    name=Column(String(80),nullable=False)
    id=Column(Integer, primary_key=True)
    user_id=Column(Integer, ForeignKey('user.id'))
    user=relationship(User)
    #for providing json endpoint
    @property
    def serialize(self):

        return {
            'name': self.name,
            'id': self.id,
            
        }
    
#Item class ->table holds all items along with their categories
class Item(Base):
    __tablename__='item'
    name=Column(String(80),nullable=False)
    id=Column(Integer,primary_key=True)
    course=Column(String(250))
    description=Column(String(250))
    category_id=Column(Integer, ForeignKey('category.id'))
    category=relationship(Category)
    user_id=Column(Integer, ForeignKey('user.id'))
    user=relationship(User)

    #for providing json endpoint
    @property
    def serialize(self):

        return {
            'name': self.name,
            'description': self.description,
            'id': self.id,
            
        }



#create the database named itemcatalog    
engine=create_engine('sqlite:///itemcatalog.db')

Base.metadata.create_all(engine)    
    
