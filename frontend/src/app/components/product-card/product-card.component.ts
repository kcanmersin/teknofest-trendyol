import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Product } from '../../models/product.model';

@Component({
  selector: 'app-product-card',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="card border-0 shadow-lg position-relative overflow-hidden product-card" 
         style="transition: all 0.3s ease; border-radius: 20px; display: flex; flex-direction: column;">
      
      <!-- Discount Badge -->
      <div *ngIf="product.discount_percentage" 
           class="position-absolute top-0 start-0 m-2" style="z-index: 10;">
        <div class="discount-badge position-relative">
          <div class="badge-content d-flex align-items-center justify-content-center text-white fw-bold">
            <div class="d-flex align-items-baseline">
              <span style="font-size: 12px; line-height: 1; margin-right: 1px;">%</span>
              <span style="font-size: 20px; line-height: 1;">{{ Math.round(product.discount_percentage) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Favorite Button -->
      <div class="position-absolute top-0 end-0 m-3" style="z-index: 10;">
        <button class="btn btn-light btn-sm rounded-circle shadow-sm" 
                style="width: 40px; height: 40px; backdrop-filter: blur(10px); background: rgba(255,255,255,0.9) !important;">
          <i class="far fa-heart"></i>
        </button>
      </div>
      
      <!-- Product Image -->
      <div class="product-image-container position-relative overflow-hidden">
        <div class="image-wrapper">
          <img [src]="product.image_url" 
               [alt]="product.content_title"
               class="product-image w-100 h-100"
               (error)="onImageError($event)"
               (mouseenter)="onImageHover($event, true)"
               (mouseleave)="onImageHover($event, false)"
               loading="lazy">
        </div>
      </div>
      
      <div class="card-body p-4 d-flex flex-column" style="flex: 1;">
        <!-- Category Badge -->
        <div class="mb-3">
          <div class="d-flex flex-wrap gap-1">
            <span class="badge text-white rounded-pill px-2 py-1 shadow-sm" 
                  style="background: linear-gradient(45deg, #0f766e, #059669); font-size: 12px;">
              {{ product.level1_category_name }}
            </span>
            <span class="badge bg-secondary text-white rounded-pill px-2 py-1" 
                  style="font-size: 11px;">
              {{ product.level2_category_name }}
            </span>
          </div>
        </div>
        
        <!-- Product Title with Green Strip -->
        <div class="position-relative mb-3">
          <div class="bg-success rounded-end-pill position-absolute top-0 start-0" 
               style="width: 4px; height: 100%; z-index: 1;"></div>
          <h5 class="card-title fw-bold ps-3" 
              style="line-height: 1.4; height: 2.8em; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; background: linear-gradient(135deg, #0f766e10, #05966905); padding: 8px 12px; border-radius: 12px; margin: 0; font-size: 1.1rem;"
              [title]="product.content_title">
            {{ product.content_title }}
          </h5>
        </div>

        <!-- Price Section -->
        <div class="mb-3">
          <div class="d-flex align-items-center justify-content-between">
            <div>
              <div class="text-success fw-bold" style="font-size: 1.3rem;">₺{{ formatPrice(product.discounted_price) }}</div>
              <div *ngIf="product.original_price !== product.discounted_price" 
                   class="position-relative d-inline-block">
                <span class="original-price text-muted small">
                  ₺{{ formatPrice(product.original_price) }}
                </span>
              </div>
            </div>
            <div class="text-end">
              <div class="text-warning small">
                <i class="fas fa-star" *ngFor="let star of getStars(product.content_rate_avg || 0)"></i>
                <i class="far fa-star" *ngFor="let star of getEmptyStars(product.content_rate_avg || 0)"></i>
              </div>
              <span class="text-muted" style="font-size: 14px;">({{ product.content_review_count }} yorum)</span>
            </div>
          </div>
        </div>
        
        <!-- Product Details -->
        <div class="bg-light bg-opacity-50 p-2 rounded-3 mb-2" style="border-left: 4px solid #0f766e;">
          <div class="row g-1" style="font-size: 13px;">
            <div class="col-12">
              <span class="text-muted">Kategori:</span> 
              {{ product.level2_category_name }}
            </div>
            <div class="col-12">
              <span class="text-muted">Alt Kategori:</span> 
              {{ product.leaf_category_name }}
            </div>
            <div class="col-6">
              <span class="text-muted">Satıcı:</span> 
              <span class="badge text-white" style="background: linear-gradient(45deg, #0f766e, #059669);">{{ product.merchant_count || 0 }}</span>
            </div>
            <div class="col-6">
              <span class="text-muted">Oy:</span> 
              <span class="badge text-white" style="background: linear-gradient(45deg, #0f766e, #059669);">{{ product.content_rate_count }}</span>
            </div>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="d-flex gap-2 mt-auto">
          <button class="btn btn-outline-primary btn-sm rounded-pill flex-fill">
            <i class="fas fa-eye me-1"></i>Detay
          </button>
          <button class="btn btn-primary btn-sm rounded-pill flex-fill" 
                  style="background: linear-gradient(45deg, #0f766e, #059669); border: none;">
            <i class="fas fa-external-link-alt me-1"></i>Git
          </button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .discount-badge {
      position: relative;
    }
    
    .discount-badge::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: linear-gradient(135deg, #dc2626 0%, #b91c1c 50%, #991b1b 100%);
      border-radius: 12px;
      transform: rotate(-8deg);
      animation: pulse-discount 2s infinite;
    }
    
    .discount-badge::after {
      content: '';
      position: absolute;
      top: 2px;
      left: 2px;
      right: 2px;
      bottom: 2px;
      background: linear-gradient(135deg, #ef4444 0%, #dc2626 50%, #b91c1c 100%);
      border-radius: 10px;
      transform: rotate(-8deg);
      box-shadow: inset 0 1px 2px rgba(255,255,255,0.3);
    }
    
    .badge-content {
      position: relative;
      z-index: 3;
      width: 55px;
      height: 55px;
      background: transparent;
      border-radius: 12px;
    }
    
    @keyframes pulse-discount {
      0%, 100% { 
        box-shadow: 0 0 10px rgba(220, 38, 38, 0.6); 
      }
      50% { 
        box-shadow: 0 0 20px rgba(220, 38, 38, 0.8), 0 0 30px rgba(220, 38, 38, 0.4); 
      }
    }
    
    .discount-badge:hover::before,
    .discount-badge:hover::after {
      transform: rotate(-5deg) scale(1.05);
      transition: all 0.3s ease;
    }
    
    .original-price {
      position: relative;
      background: linear-gradient(45deg, #f8fafc, #e2e8f0);
      padding: 2px 8px;
      border-radius: 6px;
      border: 1px solid #e2e8f0;
    }
    
    .original-price::before {
      content: '';
      position: absolute;
      top: 50%;
      left: 2px;
      right: 2px;
      height: 2px;
      background: linear-gradient(90deg, #ef4444, #dc2626, #ef4444);
      transform: translateY(-50%) rotate(-2deg);
      border-radius: 1px;
      animation: strike-through 0.8s ease forwards;
    }
    
    .original-price::after {
      content: '';
      position: absolute;
      top: 50%;
      left: 2px;
      right: 2px;
      height: 1px;
      background: #ffffff;
      transform: translateY(-50%) rotate(-2deg);
      border-radius: 0.5px;
      animation: strike-through 0.8s ease 0.2s forwards;
    }
    
    @keyframes strike-through {
      0% {
        width: 0;
        left: 50%;
        right: 50%;
      }
      100% {
        width: calc(100% - 4px);
        left: 2px;
        right: 2px;
      }
    }
    
    /* Product Image Styles - Smaller default height */
    .product-image-container {
      height: 200px;
      background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
      border-bottom: 1px solid rgba(226, 232, 240, 0.3);
    }
    
    .image-wrapper {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 8px;
    }
    
    .product-image {
      object-fit: contain;
      object-position: center;
      max-width: 100%;
      max-height: 100%;
      border-radius: 8px;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
      background: white;
    }
    
    .product-image:hover {
      transform: scale(1.03);
      box-shadow: 0 8px 25px rgba(0, 0, 0, 0.12);
    }
    
    /* Responsive card and image adjustments - Smaller cards */
    .product-card {
      height: 100%;
      min-height: 420px;
    }
    
    @media (min-width: 1400px) {
      .product-card {
        min-height: 450px;
      }
      
      .product-image-container {
        height: 200px;
      }
    }
    
    @media (max-width: 1199px) {
      .product-card {
        min-height: 400px;
      }
      
      .product-image-container {
        height: 180px;
      }
    }
    
    @media (max-width: 991px) {
      .product-card {
        min-height: 380px;
      }
      
      .product-image-container {
        height: 160px;
      }
    }
    
    @media (max-width: 767px) {
      .product-card {
        min-height: 360px;
      }
      
      .product-image-container {
        height: 140px;
      }
      
      .image-wrapper {
        padding: 6px;
      }
    }
    
    @media (max-width: 575px) {
      .product-card {
        min-height: 340px;
      }
      
      .product-image-container {
        height: 120px;
      }
      
      .card-body {
        padding: 12px !important;
      }
    }
  `]
})
export class ProductCardComponent {
  @Input() product!: Product;
  Math = Math;

  onImageError(event: any) {
    const placeholder = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjgwIiBoZWlnaHQ9IjIwMCIgdmlld0JveD0iMCAwIDI4MCAyMDAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIyODAiIGhlaWdodD0iMjAwIiBmaWxsPSIjRjhGOUZBIi8+CjxwYXRoIGQ9Ik0xNDAgODBMMTIwIDEwMEwxNjAgMTAwWiIgZmlsbD0iIzY5NzU4QiIvPgo8Y2lyY2xlIGN4PSIxMDAiIGN5PSI2MCIgcj0iMTAiIGZpbGw9IiM2OTc1OEIiLz4KPHRleHQgeD0iMTQwIiB5PSIxMzAiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzY5NzU4QiI+R8O2cnNlbCBZb2s8L3RleHQ+Cjwvc3ZnPgo=';
    event.target.src = placeholder;
    event.target.style.objectFit = 'contain';
    event.target.style.background = '#f8f9fa';
    event.target.style.border = '1px dashed #cbd5e1';
  }

  onImageHover(event: any, isHover: boolean) {
    // CSS hover efekti kullanıyoruz, JavaScript hover'ı kaldırdık
  }

  getStars(rating: number): number[] {
    const stars = Math.floor(rating);
    return Array(Math.min(stars, 5)).fill(0);
  }

  getEmptyStars(rating: number): number[] {
    const emptyStars = 5 - Math.floor(rating);
    return Array(Math.max(emptyStars, 0)).fill(0);
  }

  formatPrice(price: number): string {
    return price.toFixed(2);
  }
}