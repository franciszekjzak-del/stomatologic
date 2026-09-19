from contextvars import ContextVar
from typing import Optional

_clinic_ctx: ContextVar[Optional[str]] = ContextVar("clinic_id", default=None)


def set_clinic(cid: Optional[str]):
    return _clinic_ctx.set(cid)


def get_clinic() -> Optional[str]:
    return _clinic_ctx.get()


class TenantCollection:
    """Wraps a Motor collection and scopes every query/insert to the current clinic."""

    def __init__(self, coll):
        self._c = coll

    def _f(self, filt=None) -> dict:
        filt = dict(filt or {})
        cid = get_clinic()
        if cid:
            filt["clinic_id"] = cid
        return filt

    def _doc(self, doc: dict) -> dict:
        cid = get_clinic()
        if cid:
            doc["clinic_id"] = cid
        return doc

    def find(self, filt=None, *a, **k):
        return self._c.find(self._f(filt), *a, **k)

    async def find_one(self, filt=None, *a, **k):
        return await self._c.find_one(self._f(filt), *a, **k)

    async def count_documents(self, filt=None, *a, **k):
        return await self._c.count_documents(self._f(filt), *a, **k)

    async def insert_one(self, doc, *a, **k):
        return await self._c.insert_one(self._doc(doc), *a, **k)

    async def insert_many(self, docs, *a, **k):
        return await self._c.insert_many([self._doc(d) for d in docs], *a, **k)

    async def update_one(self, filt, upd, *a, **k):
        return await self._c.update_one(self._f(filt), upd, *a, **k)

    async def update_many(self, filt, upd, *a, **k):
        return await self._c.update_many(self._f(filt), upd, *a, **k)

    async def delete_one(self, filt, *a, **k):
        return await self._c.delete_one(self._f(filt), *a, **k)

    async def delete_many(self, filt, *a, **k):
        return await self._c.delete_many(self._f(filt), *a, **k)

    def __getattr__(self, name):
        return getattr(self._c, name)


class TenantDB:
    def __init__(self, raw):
        self.raw = raw

    def __getattr__(self, name):
        return TenantCollection(self.raw[name])

    def __getitem__(self, name):
        return TenantCollection(self.raw[name])
