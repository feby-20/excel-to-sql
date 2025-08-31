create .env and copy this:
  MYSQL_URL=mysql+pymysql://root:raimu123@localhost:3306/test
  TABLE_NAME=data_timbang
  # kolom yang sering kamu filter → nanti akan dibuatkan saran index kalau ada
  INDEX_CANDIDATES=Type,ItemCode,ItemName,CardName,Transportir,Nopol
