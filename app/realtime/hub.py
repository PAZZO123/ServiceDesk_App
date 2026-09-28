#this keeps a list of who is connected and which they are in
import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

QUEUE_SIZE=100

RESYNC: dict[str, Any]={"type":"resync"}

@dataclass(eq=False)
class Subscriber:
    #One Open connection in this process
    rooms:frozenset[str]
    queue:asyncio.Queue[dict[str, Any]]=field(
        default_factory=lambda:asyncio.Queue(maxsize=QUEUE_SIZE)
    )
    missed:bool=False
    async def get(self)->dict[str, Any]:
        message=await self.queue.get()
        if self.missed:
            self.missed=False
            while not self.queue.empty():
                self.queue.get_nowait()
            return RESYNC
        return message
    
class Hub:
    #Which Connection listens to which room. Lives in mmry per process
    def __init__(self) ->None:
        self._rooms: dict[str, set[Subscriber]]=defaultdict(set)
        
    def subscribe(self, rooms:set[str])->Subscriber:
        subscriber=Subscriber(rooms=frozenset(rooms))
        for room in subscriber.rooms:
            self._rooms[room].add(subscriber)
        return subscriber
    
    def unsubscribe(self, subscriber:Subscriber)->None:
        for room in subscriber.rooms:
            members=self._rooms.get(room)
            if members is None:
                continue
            members.discard(subscriber)
            if not members:
                del self._rooms[room]
            
    def dispatch(self, rooms: list[str], message: dict[str, Any]) -> None:
        targets: set[Subscriber] = set()
        for room in rooms:
            targets |= self._rooms.get(room, set())
        for subscriber in targets:
            self._deliver(subscriber, message)

    def broadcast(self, message: dict[str, Any]) -> None:
        everyone = set().union(*self._rooms.values())
        for subscriber in everyone:
            self._deliver(subscriber, message)
            
    @staticmethod
    def _deliver(subscriber:Subscriber, message:dict[str, Any])->None:
        #put nowait so that one slow browser must not hold up the rest.
        try:
            subscriber.queue.put_nowait(message)
        except asyncio.QueueFull:
            subscriber.missed =True
            

hub=Hub()