# Excel to SQL (for check kolom, dan type kolom)

## Setup

Buat file `.env` dan isi seperti berikut:

```env
MYSQL_URL=mysql+pymysql://root:raimu123@localhost:3306/test
TABLE_NAME=data_timbang
INDEX_CANDIDATES=Type,ItemCode,ItemName,CardName,Transportir,Nopol
