from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Enumeration, EnumValue
from .schemas import (
    EnumerationCreate,
    EnumerationOut,
    EnumerationUpdate,
    ValidationResult,
    ValueIn,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Enumeration Manager", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_or_404(db: Session, name: str) -> Enumeration:
    enum = db.scalar(select(Enumeration).where(Enumeration.name == name))
    if enum is None:
        raise HTTPException(status_code=404, detail=f"Enumeration '{name}' not found")
    return enum


def _ensure_name_free(db: Session, name: str) -> None:
    if db.scalar(select(Enumeration.id).where(Enumeration.name == name)) is not None:
        raise HTTPException(status_code=409, detail=f"Enumeration '{name}' already exists")


def _set_values(db: Session, enum: Enumeration, values: list[str]) -> None:
    if enum.values:
        enum.values.clear()
        # SQLAlchemy emits INSERTs before DELETEs in a single flush, which would trip the
        # unique (enumeration_id, value) constraint when old and new lists overlap.
        db.flush()
    enum.values.extend(EnumValue(value=v, position=i) for i, v in enumerate(values))


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/enumerations", response_model=list[EnumerationOut])
def list_enumerations(db: Session = Depends(get_db)):
    return db.scalars(select(Enumeration).order_by(Enumeration.name)).all()


@app.post("/api/enumerations", response_model=EnumerationOut, status_code=status.HTTP_201_CREATED)
def create_enumeration(payload: EnumerationCreate, db: Session = Depends(get_db)):
    _ensure_name_free(db, payload.name)
    enum = Enumeration(name=payload.name, description=payload.description)
    _set_values(db, enum, payload.values)
    db.add(enum)
    db.commit()
    db.refresh(enum)
    return enum


@app.get("/api/enumerations/{name}", response_model=EnumerationOut)
def get_enumeration(name: str, db: Session = Depends(get_db)):
    return _get_or_404(db, name)


@app.put("/api/enumerations/{name}", response_model=EnumerationOut)
def update_enumeration(name: str, payload: EnumerationUpdate, db: Session = Depends(get_db)):
    enum = _get_or_404(db, name)
    fields = payload.model_fields_set

    if payload.name is not None and payload.name != enum.name:
        _ensure_name_free(db, payload.name)
        enum.name = payload.name
    if "description" in fields:
        enum.description = payload.description
    if payload.values is not None:
        _set_values(db, enum, payload.values)

    db.commit()
    db.refresh(enum)
    return enum


@app.delete("/api/enumerations/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_enumeration(name: str, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, name))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/enumerations/{name}/values", response_model=EnumerationOut, status_code=status.HTTP_201_CREATED)
def add_value(name: str, payload: ValueIn, db: Session = Depends(get_db)):
    enum = _get_or_404(db, name)
    if any(v.value == payload.value for v in enum.values):
        raise HTTPException(status_code=409, detail=f"Value '{payload.value}' already exists in '{name}'")
    next_pos = max((v.position for v in enum.values), default=-1) + 1
    enum.values.append(EnumValue(value=payload.value, position=next_pos))
    db.commit()
    db.refresh(enum)
    return enum


@app.delete("/api/enumerations/{name}/values/{value}", response_model=EnumerationOut)
def remove_value(name: str, value: str, db: Session = Depends(get_db)):
    enum = _get_or_404(db, name)
    match = next((v for v in enum.values if v.value == value), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Value '{value}' not found in '{name}'")
    if len(enum.values) == 1:
        raise HTTPException(status_code=400, detail="An enumeration must keep at least one value")
    enum.values.remove(match)
    db.commit()
    db.refresh(enum)
    return enum


@app.get("/api/enumerations/{name}/validate", response_model=ValidationResult)
def validate_value(name: str, value: str, db: Session = Depends(get_db)):
    enum = _get_or_404(db, name)
    return ValidationResult(
        enumeration=name,
        value=value,
        valid=any(v.value == value for v in enum.values),
    )
