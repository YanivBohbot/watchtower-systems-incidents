"""Sites and cameras come from a seed file; there is no admin UI for them yet."""

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.database.models import Camera, Site
from app.domain.dwell_rule import Zone


class CameraSeed(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source: str = Field(min_length=1)
    zone: Zone | None = None
    labels: list[str] = []
    enabled: bool = True


class SiteSeed(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    fictional: bool = False
    cameras: list[CameraSeed]


def seed_site(sessions, data: dict) -> str:
    """Create or update a site and its cameras by name; re-running never duplicates rows."""
    seed = SiteSeed.model_validate(data)
    with sessions() as db:
        site = db.scalar(select(Site).where(Site.name == seed.name))
        if site is None:
            site = Site(name=seed.name)
            db.add(site)
            db.flush()
        for item in seed.cameras:
            camera = db.scalar(select(Camera).where(Camera.site_id == site.id, Camera.name == item.name))
            if camera is None:
                camera = Camera(site_id=site.id, name=item.name)
                db.add(camera)
            camera.source = item.source
            camera.zone = item.zone.model_dump() if item.zone else None
            camera.labels = list(item.labels)
            camera.enabled = item.enabled
        db.commit()
        return site.id
