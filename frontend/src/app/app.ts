import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClientModule } from '@angular/common/http';
import { ProductService } from './services/product.service';
import { Product } from './models/product.model';
import { SearchBarComponent } from './components/search-bar/search-bar.component';
import { LoadingSpinnerComponent } from './components/loading-spinner/loading-spinner.component';
import { ProductCardComponent } from './components/product-card/product-card.component';
import { ProductListComponent } from './components/product-list/product-list.component';
import { CategorySidebarComponent } from './components/category-sidebar/category-sidebar.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    HttpClientModule,
    SearchBarComponent,
    LoadingSpinnerComponent,
    ProductCardComponent,
    ProductListComponent,
    CategorySidebarComponent
  ],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App implements OnInit {
  products: Product[] = [];
  isLoading = false;
  selectedCategories: string[] = [];
  currentQuery = '';
  viewMode: 'grid' | 'list' = 'grid';

  constructor(private productService: ProductService) {}

  ngOnInit() {
    // Component initialized
  }

  setViewMode(mode: 'grid' | 'list') {
    this.viewMode = mode;
  }

  onSearch(query: string) {
    this.currentQuery = query;
    this.performSearch();
  }

  onCategoryFilter(categories: string[]) {
    console.log('🎯 FRONTEND: Category filter received:', categories);
    this.selectedCategories = categories;
    this.performSearch();
  }

  performSearch() {
    if (!this.currentQuery && this.selectedCategories.length === 0) {
      this.products = [];
      return;
    }

    this.isLoading = true;

    // Kategori filtresi varsa advanced search kullan
    if (this.selectedCategories.length > 0) {
      const searchParams: any = {
        query: this.currentQuery || '',
        limit: 50
      };

      // Seçili kategoriler için çoklu filtreleme (OR logic)
      if (this.selectedCategories.length > 0) {
        // Çoklu kategori listesi gönder
        searchParams.category_level2_list = this.selectedCategories;
        console.log('🚀 FRONTEND: Sending multi-category search with category_level2_list:', searchParams.category_level2_list);
        // Query'yi temizle - sadece kategori filtresini kullan
        searchParams.query = '';
      }

      this.productService.advancedSearch(searchParams).subscribe({
        next: (data) => {
          this.products = data.products;
          this.isLoading = false;
        },
        error: (error) => {
          this.products = [];
          this.isLoading = false;
        }
      });
    } else {
      // Normal arama
      this.productService.searchProducts(this.currentQuery).subscribe({
        next: (data) => {
          this.products = data.products;
          this.isLoading = false;
        },
        error: (error) => {
          this.products = [];
          this.isLoading = false;
        }
      });
    }
  }

  onTest() {
    // Placeholder for test function
  }

  onRefresh() {
    // Placeholder for refresh function
  }

}
