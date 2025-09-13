import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClientModule } from '@angular/common/http';
import { Router, ActivatedRoute } from '@angular/router';
import { ProductService } from './services/product.service';
import { Product } from './models/product.model';
import { SearchBarComponent } from './components/search-bar/search-bar.component';
import { ProductCardComponent } from './components/product-card/product-card.component';
import { CategorySidebarComponent } from './components/category-sidebar/category-sidebar.component';
import { ProductModalComponent } from './components/product-modal/product-modal.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    HttpClientModule,
    SearchBarComponent,
    ProductCardComponent,
    CategorySidebarComponent,
    ProductModalComponent
  ],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App implements OnInit {
  products: Product[] = [];
  isLoading = false;
  selectedCategories: string[] = [];
  currentQuery = '';
  categoryFilterQuery = ''; // For real-time category filtering
  
  // Modal properties
  selectedProduct: Product | null = null;
  isModalVisible = false;

  constructor(
    private productService: ProductService,
    private router: Router,
    private route: ActivatedRoute
  ) {}

  ngOnInit() {
    // Check for product ID in URL on init
    this.route.queryParams.subscribe(params => {
      const productId = params['product'];
      if (productId) {
        // Find and open product modal if ID exists
        // Note: You might want to load product by ID from backend
        console.log('Product ID from URL:', productId);
      }
    });
  }



  onSearch(query: string) {
    this.currentQuery = query;
    this.performSearch();
  }
  
  onQueryChange(query: string) {
    // Real-time category filtering without search
    this.categoryFilterQuery = query;
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

      // ML mode kullan
      searchParams.mode = 'ml';
      
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
      // Normal arama - ML mode kullan
      this.productService.searchProducts(this.currentQuery, 50, 'ml').subscribe({
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

  // Modal methods
  openProductModal(product: Product) {
    this.selectedProduct = product;
    this.isModalVisible = true;
    
    // Update URL with product ID
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { product: product.content_id_hashed },
      queryParamsHandling: 'merge'
    });
  }

  closeProductModal() {
    this.isModalVisible = false;
    this.selectedProduct = null;
    
    // Remove product ID from URL
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { product: null },
      queryParamsHandling: 'merge'
    });
  }

}
