import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Product, SearchResponse, ApiResponse } from '../models/product.model';

@Injectable({
  providedIn: 'root'
})
export class ProductService {
  private readonly API_BASE = 'https://ff7da232da70.ngrok-free.app';
  private readonly headers = new HttpHeaders({
    'ngrok-skip-browser-warning': 'true',
    'Content-Type': 'application/json'
  });

  constructor(private http: HttpClient) {}

  testAPI(): Observable<ApiResponse> {
    return this.http.get<ApiResponse>(`${this.API_BASE}/`, { 
      headers: this.headers 
    });
  }

  searchProducts(query: string, limit: number = 50, mode: string = 'ml'): Observable<SearchResponse> {
    return this.http.post<SearchResponse>(`${this.API_BASE}/search`, 
      { query, limit, mode }, 
      { headers: this.headers }
    );
  }

  getCategories(): Observable<any> {
    return this.http.get<any>(`${this.API_BASE}/categories`, { 
      headers: this.headers 
    });
  }

  getGroupedCategories(): Observable<any> {
    return this.http.get<any>(`${this.API_BASE}/categories/grouped`, { 
      headers: this.headers 
    });
  }

  getPopularCategories(limit: number = 10): Observable<any> {
    return this.http.get<any>(`${this.API_BASE}/popular-categories?limit=${limit}`, { 
      headers: this.headers 
    });
  }

  advancedSearch(params: {
    query?: string,
    category_level1?: string,
    category_level2?: string,
    category_leaf?: string,
    min_price?: number,
    max_price?: number,
    min_rating?: number,
    min_review_count?: number,
    limit?: number,
    mode?: string
  }): Observable<SearchResponse> {
    return this.http.post<SearchResponse>(`${this.API_BASE}/search/advanced`, params, { 
      headers: this.headers 
    });
  }

  refreshData(): Observable<ApiResponse> {
    return this.http.post<ApiResponse>(`${this.API_BASE}/refresh`, {}, { 
      headers: this.headers 
    });
  }

  getAutocomplete(query: string): Observable<any> {
    return this.http.get<any>(`${this.API_BASE}/autocomplete?q=${encodeURIComponent(query)}`, { 
      headers: this.headers 
    });
  }
}