from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import mysql.connector

@dataclass
class MySQLConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    bar_table: str
    alert_table: str

class MySQLWriter:
    def __init__(self, cfg: MySQLConfig):
        self.cfg = cfg
        self.conn = mysql.connector.connect(
            host=cfg.host,
            port=cfg.port,
            user=cfg.user,
            password=cfg.password,
            database=cfg.database,
            autocommit=True,
        )

    def insert_bars(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        cols = list(rows[0].keys())
        ph = ",".join(["%s"] * len(cols))
        sql = f"INSERT INTO {self.cfg.bar_table} ({','.join(cols)}) VALUES ({ph})"
        vals = [tuple(r.get(c) for c in cols) for r in rows]
        cur = self.conn.cursor()
        cur.executemany(sql, vals)
        cur.close()

    def insert_alert(self, symbol: str, sec: int, side: str,
                     prob: float, pred_ret: float, thr: float,
                     mid: float, spread: float, message: str) -> None:
        sql = f"""INSERT INTO {self.cfg.alert_table}
                  (symbol, sec, side, prob, pred_ret, thr, mid, spread, message)
                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
        cur = self.conn.cursor()
        cur.execute(sql, (symbol, sec, side, prob, pred_ret, thr, mid, spread, message))
        cur.close()
