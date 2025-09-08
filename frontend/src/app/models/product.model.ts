export interface Product {
  content_id_hashed: string;
  content_title: string;
  level1_category_name: string;
  level2_category_name: string;
  leaf_category_name: string;
  merchant_count?: number;
  original_price: number;
  selling_price: number;
  discounted_price: number;
  content_review_count: number;
  content_rate_count: number;
  content_rate_avg?: number;
  discount_percentage?: number;
  image_url: string;
  // ML-specific fields
  tfidf_sim?: number;
  score?: number;
}

export interface SearchResponse {
  products: Product[];
  total_results: number;
}

export interface ApiResponse {
  message: string;
  status: string;
  total_products?: number;
}