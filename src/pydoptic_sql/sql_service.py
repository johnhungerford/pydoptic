

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Generic, Iterator, List, Sequence, Tuple, Type, cast

from pydoptic.base_model import PartialModel
from pydoptic.selector import PropSelect
from pydoptic_sql import SqlQuery
from pydoptic_sql.sql_query import TC, R, SelectQuery

from psycopg import Connection, Cursor


class SqlClient:
    @contextmanager
    def open(self) -> Iterator['SqlTransaction']:
        raise NotImplementedError()

class SqlResponse(Generic[R]):
    def fetchone(self) -> R | None:
        raise NotImplementedError()

    def stream(self) -> Iterator[R]:
        raise NotImplementedError()

class SqlTransaction:
    def commit(self) -> None:
        raise NotImplementedError()

    def rollback(self) -> None:
        raise NotImplementedError()

    def close(self) -> None:
        raise NotImplementedError()

    def execute(self, query: SqlQuery[R]) -> SqlResponse[R]:
        raise NotImplementedError()

class EmptyPgSqlResponse(SqlResponse[R]):
    def fetchone(self) -> R | None:
        return None

    def stream(self) -> Iterator[R]:
        seq: Sequence[R] = []
        return iter(seq)

@dataclass
class PsycoPgSqlResponse(Generic[TC], SqlResponse[PartialModel[TC]]):
    model: Type[TC]
    cursor: Cursor
    selection: List[PropSelect[TC, Any]]

    def __make_record(self, sql_record: Tuple[Any,...]) -> PartialModel[TC]:
        data: Dict[str, Any] = {}
        for i, prop in enumerate(self.selection):
            data[prop.label] = sql_record[i]
        return PartialModel(self.model, **data)

    def fetchone(self) -> PartialModel[TC] | None:
        result = self.cursor.fetchone()
        if result is not None:
            return self.__make_record(result)
        return None
    
    def stream(self) -> Iterator[PartialModel[TC]]:
        for row in self.cursor:
            yield self.__make_record(row)

@dataclass
class PsycoPgSqlTransaction(SqlTransaction):
    connection: Connection
    cursor: Cursor

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()
    
    def close(self) -> None:
        self.cursor.close()
    
    def execute(self, query: SqlQuery[R]) -> SqlResponse[R]:
        self.cursor.execute(query.to_sql())
        match query:
            case SelectQuery():
                # SelectQuery[TC]'s R is always PartialModel[TC], which is exactly the caller's R here,
                # but match narrowing can't invert R back to TC to prove that statically.
                return cast(SqlResponse[R], PsycoPgSqlResponse(query._model, self.cursor, query._selection))
            case _:
                return EmptyPgSqlResponse()

@dataclass(frozen=True)
class PsycoPgSqlClient(SqlClient):
    connection: Connection

    @contextmanager
    def open(self) -> Iterator['SqlTransaction']:
        with self.connection.cursor() as cursor:
            yield PsycoPgSqlTransaction(self.connection, cursor)
