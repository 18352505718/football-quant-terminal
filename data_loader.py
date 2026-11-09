"""
数据接入模块:
支持加载公开标准的比赛数据源 (如 football-data.co.uk CSV 文件或自定义 DataFrame)。
自动解析比赛日期并计算 days_ago 时间衰减距离。
"""

import pandas as pd
from datetime import datetime


class MatchDataLoader:
    @staticmethod
    def load_from_football_data_co_uk(csv_path_or_url: str, reference_date: str = None) -> pd.DataFrame:
        """
        加载标准 football-data.co.uk 格式数据 (如 E0.csv, SP1.csv)
        标准列名: Date, HomeTeam, AwayTeam, FTHG, FTAG
        """
        df = pd.read_csv(csv_path_or_url)
        
        # 兼容日期解析 (常见格式 dd/mm/yyyy 或 dd/mm/yy)
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True)
        
        if reference_date is None:
            ref_dt = df['Date'].max()
        else:
            ref_dt = pd.to_datetime(reference_date)

        df['days_ago'] = (ref_dt - df['Date']).dt.total_seconds() / (24 * 3600)
        # 剔除未来赛事未赛场次
        df = df.dropna(subset=['FTHG', 'FTAG'])

        cleaned = pd.DataFrame({
            'date': df['Date'],
            'home_team': df['HomeTeam'].astype(str).str.strip(),
            'away_team': df['AwayTeam'].astype(str).str.strip(),
            'home_goals': df['FTHG'].astype(int),
            'away_goals': df['FTAG'].astype(int),
            'days_ago': df['days_ago'].clip(lower=0)
        })
        return cleaned

    @staticmethod
    def create_dataframe_from_records(records: list, reference_date: datetime = None) -> pd.DataFrame:
        """从字典列表快速构造输入"""
        df = pd.DataFrame(records)
        if 'days_ago' not in df.columns:
            if 'date' in df.columns:
                ref = reference_date or datetime.now()
                df['date'] = pd.to_datetime(df['date'])
                df['days_ago'] = (ref - df['date']).dt.total_seconds() / (24 * 3600)
            else:
                df['days_ago'] = 0.0
        return df
