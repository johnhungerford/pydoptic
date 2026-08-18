from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, ClassVar, Generic, List, NotRequired, Type, TypeVar, TypedDict, Unpack
from pydoptic import BaseModel, select
from pydoptic.selector import PropSelect

A = TypeVar('A')

class SqlTable(BaseModel):
    table_name: ClassVar[str]

T = TypeVar('T', bound=SqlTable)

class ColumnType:
    def to_sql(self) -> str:
        raise NotImplementedError()

    @classmethod
    def from_type(cls, type: Type[Any]):
        if type is int:
            return cls.INT()
        if type is str:
            return cls.TEXT()
        if type is bool:
            return cls.BOOL()
        if type is float:
            return cls.REAL()
        if type is date:
            return cls.DATE()
        if type is datetime:
            return cls.DATE()
        raise ValueError(f'Unknown column type: {type}')
        

    @classmethod
    def INT(cls) -> 'Int':
        return Int.Int
    
    @classmethod
    def SMALLINT(cls) -> 'Int':
        return Int.SmallInt
    
    @classmethod
    def BIGINT(cls) -> 'Int':
        return Int.BigInt
    
    @classmethod
    def REAL(cls) -> 'Float':
        return Float.Real
    
    @classmethod
    def DOUBLE(cls) -> 'Float':
        return Float.Double
    
    @classmethod
    def BOOL(cls) -> 'OtherType':
        return OtherType.Bool
    
    @classmethod
    def BLOB(cls) -> 'OtherType':
        return OtherType.Blob
    
    @classmethod
    def UUID(cls) -> 'OtherType':
        return OtherType.UUID
    
    @classmethod
    def JSON(cls) -> 'OtherType':
        return OtherType.Json
    
    @classmethod
    def DATE(cls) -> 'OtherType':
        return OtherType.Date
    
    @classmethod
    def TEXT(cls, unicode: bool = False) -> 'Text':
        return Text.NText if unicode else Text.Text

    @classmethod
    def CHAR(cls, size: int, unicode: bool = False) -> 'Char':
        return Char(size, unicode)
    
    @classmethod
    def VARCHAR(cls, size: int, unicode: bool = False) -> 'VarChar':
        return VarChar(size, unicode)
    

@dataclass(frozen=True)
class Char(ColumnType):
    size: int
    unicode: bool = False

    def to_sql(self) -> str:
        if self.unicode:
            return f'NCHAR({self.size})'
        return f'CHAR({self.size})'

@dataclass(frozen=True)
class VarChar(ColumnType):
    size: int
    unicode: bool = False

    def to_sql(self) -> str:
        if self.unicode:
            return f'NVARCHAR({self.size})'
        return f'VARCHAR({self.size})'

class Int(ColumnType, Enum):
    Int = 'INTEGER'
    SmallInt = 'SMALLINT'
    BigInt = 'BIGINT'

    def to_sql(self) -> str:
        return self.value

class Float(ColumnType, Enum):
    Real = 'REAL'
    Double = 'DOUBLE PRECISION'

    def to_sql(self) -> str:
        return self.value

class Text(ColumnType, Enum):
    Text = 'TEXT'
    NText = 'NTEXT'

    def to_sql(self) -> str:
        return self.value

class OtherType(ColumnType, Enum):
    Bool = 'BOOLEAN'
    UUID = 'UUID' # type: ignore[assignment]
    Json = 'JSON'
    Blob = 'BLOB'
    Date = 'DATE'

    def to_sql(self) -> str:
        return self.value

@dataclass(frozen=True)
class ManualColumnType(ColumnType):
    type: str

@dataclass(frozen=True)
class ColumnConstraint:
    ...

@dataclass(frozen=True)
class __PrimaryKey(ColumnConstraint):
    ...

PrimaryKey = __PrimaryKey()

@dataclass(frozen=True)
class __Unique(ColumnConstraint):
    ...

Unique = __Unique()

@dataclass(frozen=True)
class __AutoIncrement(ColumnConstraint):
    ...

AutoIncrement = __AutoIncrement()

@dataclass(frozen=True)
class ForeignKey(Generic[T, A], ColumnConstraint):
    references: PropSelect[T, A]

@dataclass(frozen=True)
class Check(ColumnConstraint):
    constraint: str

@dataclass(frozen=True)
class Default(ColumnConstraint):
    value: Any

@dataclass(frozen=True)
class ManualColumnConstraint(ColumnConstraint):
    type: str

class ColumnInfo(TypedDict):
    type: NotRequired[ColumnType]
    constraints: NotRequired[List[ColumnConstraint]]

def column(name: str | None = None, **column_info: Unpack[ColumnInfo]) -> Any:
    return select(name, **column_info)
