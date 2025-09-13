# pyspark 3/4
from pyspark.sql import SparkSession, functions as F, Window
import math

spark = SparkSession.builder.appName("offline_cat_neighbors").getOrCreate()

events   = spark.read.parquet("/data/events.parquet")
products = spark.read.parquet("/data/products.parquet").select(
    "content_id_hashed", "leaf_category_name"
)

# 1) Ürün -> kategori join
ev = (events.join(products, "content_id_hashed", "inner")
             .select("session_id", "leaf_category_name", "ordered", "added_to_cart"))

# (Opsiyonel) zaman penceresi: son 30 gün gibi
# ev = ev.filter(F.col("ts_hour") >= F.current_timestamp() - F.expr("INTERVAL 30 DAYS"))

# 2) Sepet/Oturum başına kategori seti (ordered veya cart bazlı)
baskets = (ev.filter((F.col("ordered")==1) | (F.col("added_to_cart")==1))
             .groupBy("session_id")
             .agg(F.array_distinct(F.collect_list("leaf_category_name")).alias("cats"))
             .filter(F.size("cats") >= 2))

# 3) A ve B'yi oturum bazında (yönlü) oluştur: her (A,B) için A!=B
pairs = (baskets
    .select("session_id", F.explode("cats").alias("A"))
    .join(baskets.select("session_id", F.explode("cats").alias("B")), on="session_id")
    .filter(F.col("A") != F.col("B"))
    .select("A","B"))

# 4) Sayımlar
N_sessions = baskets.count()  # toplam oturum
suppA = (pairs.select("A","B").groupBy("A").agg(F.countDistinct("session_id").alias("tmp")))  # placeholder, değiştirilecek
# Yukarıdaki satırda session_id yok; alternatif: A desteklerini ayrı tablodan çıkar:
A_supp = (baskets
    .select("session_id", F.explode("cats").alias("A"))
    .groupBy("A").agg(F.countDistinct("session_id").alias("SA")))

B_supp = (baskets
    .select("session_id", F.explode("cats").alias("B"))
    .groupBy("B").agg(F.countDistinct("session_id").alias("SB")))

AB_cnt = (pairs.groupBy("A","B").agg(F.count("*").alias("CAB")))  # her oturumda (A,B) bir kez üretildi

# 5) Metrikler
# p(B|A) = CAB / SA  (association "confidence")  — association rule mining'te standarttır. :contentReference[oaicite:1]{index=1}
# lift(A->B) = p(B|A) / p(B)  ve p(B) = SB / N_sessions. :contentReference[oaicite:2]{index=2}
# PMI(A,B) = log( (CAB/N) / ((SA/N)*(SB/N)) )  — eşgörülme beklenenden ne kadar fazla? :contentReference[oaicite:3]{index=3}
# Jaccard(A,B) = CAB / (SA + SB - CAB)  — küme benzerliği. :contentReference[oaicite:4]{index=4}

from pyspark.sql.types import DoubleType

stats = (AB_cnt
    .join(A_supp, on="A", how="left")
    .join(B_supp, on="B", how="left")
    .withColumn("N", F.lit(float(N_sessions)))
    .withColumn("p_b_given_a", (F.col("CAB") / F.col("SA")).cast(DoubleType()))
    .withColumn("p_b", (F.col("SB") / F.col("N")).cast(DoubleType()))
    .withColumn("lift", (F.col("p_b_given_a") / F.col("p_b")).cast(DoubleType()))
    .withColumn("p_ab", (F.col("CAB") / F.col("N")).cast(DoubleType()))
    .withColumn("p_a", (F.col("SA") / F.col("N")).cast(DoubleType()))
    .withColumn("pmi", F.log(F.col("p_ab") / (F.col("p_a") * F.col("p_b"))))  # doğal log
    .withColumn("jaccard", (F.col("CAB") / (F.col("SA") + F.col("SB") - F.col("CAB"))).cast(DoubleType()))
)

# Gürültüyü kesmek için minimum destek eşiği (örn. en az 50 oturumda birlikte görülmüş)
MIN_CAB = 50
stats = stats.filter(F.col("CAB") >= F.lit(MIN_CAB))

# 6) A başına Top-K komşu (skor sırası: önce PMI veya lift, sonra p(B|A))
K = 20
w = Window.partitionBy("A").orderBy(F.col("pmi").desc(), F.col("lift").desc(), F.col("p_b_given_a").desc())
topk = (stats
    .withColumn("rn", F.row_number().over(w))
    .filter(F.col("rn") <= K)
    .select("A","B","p_b_given_a","lift","pmi","jaccard","CAB","SA","SB"))

# 7) JSON Lines: A -> [{B, p_b_given_a, lift, pmi, jaccard}]
out = (topk
    .groupBy("A")
    .agg(F.to_json(F.collect_list(F.struct("B","p_b_given_a","lift","pmi","jaccard"))).alias("neighbors")))

(out.coalesce(1)
    .write.mode("overwrite")
    .json("/out/cat_neighbors_jsonl"))

# (isteğe bağlı) Parquet de yaz
topk.write.mode("overwrite").parquet("/out/cat_neighbors_parquet")

spark.stop()