import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Product } from '../../models/product.model';

@Component({
  selector: 'app-product-list',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="product-list">
      <div *ngFor="let product of products; let i = index" 
           class="product-list-item bg-white rounded-2 shadow-sm mb-2 overflow-hidden"
           [style.animation-delay.ms]="i * 30"
           style="animation: fadeInUp 0.4s ease forwards; opacity: 0;">
        
        <div class="row g-0 align-items-stretch">
          <!-- Product Image -->
          <div class="col-12 col-sm-3 col-lg-2">
            <div class="list-image-container h-100 position-relative">
              <div class="list-image-wrapper h-100">
                <img [src]="product.image_url" 
                     [alt]="product.content_title"
                     class="list-product-image"
                     (error)="onImageError($event)"
                     loading="lazy">
              </div>
              
              <!-- Discount Badge -->
              <div *ngIf="product.discount_percentage" 
                   class="discount-badge-list position-absolute">
                <span class="badge-content">
                  <span class="discount-percent">%{{ Math.round(product.discount_percentage) }}</span>
                </span>
              </div>
            </div>
          </div>

          <!-- Product Info -->
          <div class="col-12 col-sm-6 col-lg-7">
            <div class="product-content py-1 px-1 h-100 d-flex flex-column justify-content-center">
              
              <!-- Title -->
              <div class="product-title-mini mb-0">
                {{ product.content_title }}
              </div>

              <!-- Rating & Category in one line -->
              <div class="d-flex align-items-center justify-content-between">
                <div class="product-rating-mini">
                  <div class="stars-mini">
                    <i class="fas fa-star" *ngFor="let star of getStars(product.content_rate_avg || 0)"></i>
                    <i class="far fa-star" *ngFor="let star of getEmptyStars(product.content_rate_avg || 0)"></i>
                  </div>
                  <span class="rating-text-mini">({{ product.content_review_count }})</span>
                </div>
                <span class="category-badge-mini">{{ product.level1_category_name }}</span>
              </div>
            </div>
          </div>

          <!-- Price & Actions -->
          <div class="col-12 col-sm-3 col-lg-3">
            <div class="price-action-section py-0 px-1 h-100 d-flex flex-column justify-content-center">
              <!-- Price & Actions in one column -->
              <div class="text-center">
                <div class="current-price-mini">₺{{ product.discounted_price | number:'1.2-2' }}</div>
                <div *ngIf="product.original_price !== product.discounted_price" 
                     class="original-price-mini">
                  ₺{{ product.original_price | number:'1.2-2' }}
                </div>
                <!-- Micro Buttons -->
                <div class="micro-buttons d-flex gap-1 justify-content-center mt-1">
                  <button class="btn-micro btn-outline">
                    <i class="fas fa-eye"></i>
                  </button>
                  <button class="btn-micro btn-primary-micro">
                    <i class="fas fa-external-link-alt"></i>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    /* Main Card Styles */
    .product-list-item {
      transition: all 0.3s ease;
      border: 1px solid #e2e8f0;
      background: white;
      position: relative;
      min-height: 80px;
    }

    .product-list-item:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(15, 118, 110, 0.15) !important;
      border-color: rgba(15, 118, 110, 0.2);
    }
    
    /* Image Container */
    .list-image-container {
      background: #f8fafc;
      border-radius: 0;
      overflow: hidden;
      position: relative;
      min-height: 80px;
    }
    
    .list-image-wrapper {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1px;
    }
    
    .list-product-image {
      object-fit: contain;
      object-position: center;
      max-width: 100%;
      max-height: 100%;
      border-radius: 12px;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      background: white;
      box-shadow: 0 8px 25px rgba(0, 0, 0, 0.08);
    }
    
    .product-list-item:hover .list-product-image {
      transform: scale(1.05);
      box-shadow: 0 12px 35px rgba(0, 0, 0, 0.12);
    }

    /* Discount Badge */
    .discount-badge-list {
      top: 8px;
      left: 8px;
      z-index: 10;
    }

    .badge-content {
      background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
      color: white;
      padding: 6px 10px;
      border-radius: 12px;
      font-weight: 700;
      font-size: 11px;
      box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
      display: inline-block;
    }

    /* Category Badges */
    .category-badge {
      padding: 1px 4px;
      border-radius: 8px;
      font-size: 8px;
      font-weight: 600;
      letter-spacing: 0.2px;
      text-transform: uppercase;
    }

    .category-badge.primary {
      background: linear-gradient(45deg, #0f766e, #059669);
      color: white;
      box-shadow: 0 2px 8px rgba(15, 118, 110, 0.3);
    }

    .category-badge.secondary {
      background: linear-gradient(45deg, #64748b, #475569);
      color: white;
      box-shadow: 0 2px 8px rgba(100, 116, 139, 0.3);
    }

    /* Product Title Mini - Larger text */
    .product-title-mini {
      color: #1e293b;
      font-weight: 600;
      line-height: 1.2;
      font-size: 0.95rem;
      margin: 0;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    /* Product Details */
    .product-details {
      background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
      padding: 12px;
      border-radius: 12px;
      border-left: 4px solid #0f766e;
    }

    .detail-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }

    .detail-row:last-child {
      margin-bottom: 0;
    }

    .detail-label {
      color: #64748b;
      font-size: 12px;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .detail-value {
      color: #1e293b;
      font-size: 13px;
      font-weight: 500;
    }

    .info-badge {
      background: linear-gradient(45deg, #3b82f6, #1d4ed8);
      color: white;
      padding: 4px 8px;
      border-radius: 8px;
      font-size: 11px;
      font-weight: 600;
    }

    /* Rating Mini */
    .product-rating-mini {
      display: flex;
      align-items: center;
      gap: 2px;
    }

    .stars-mini {
      color: #f59e0b;
      font-size: 14px;
    }

    .rating-text-mini {
      color: #64748b;
      font-size: 12px;
      font-weight: 500;
    }
    
    .category-badge-mini {
      background: #0f766e;
      color: white;
      padding: 2px 6px;
      border-radius: 8px;
      font-size: 11px;
      font-weight: 600;
    }

    /* Price Section */
    .price-action-section {
      background: #f8fafc;
      border-left: 3px solid #0f766e;
    }

    .current-price-mini {
      color: #059669;
      font-size: 1.1rem;
      font-weight: 700;
      line-height: 1;
    }

    .original-price-mini {
      color: #94a3b8;
      font-size: 0.85rem;
      text-decoration: line-through;
      font-weight: 500;
    }

    /* Micro Buttons */
    .btn-micro {
      padding: 4px;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      background: white;
      color: #64748b;
      font-size: 12px;
      transition: all 0.2s ease;
      width: 32px;
      height: 28px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
    }
    
    .btn-micro:hover {
      transform: translateY(-1px);
    }
    
    .btn-outline:hover {
      background: #0f766e;
      color: white;
      border-color: #0f766e;
    }
    
    .btn-primary-micro {
      background: #0f766e !important;
      border-color: #0f766e !important;
      color: white !important;
    }
    
    .btn-primary-micro:hover {
      background: #134e4a !important;
      border-color: #134e4a !important;
    }

    .btn-primary-gradient {
      background: linear-gradient(45deg, #0f766e, #059669) !important;
      border: none !important;
      color: white !important;
    }

    .btn-primary-gradient:hover {
      background: linear-gradient(45deg, #134e4a, #047857) !important;
      transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(15, 118, 110, 0.4);
    }

    .btn-outline-primary:hover {
      background: #0f766e;
      border-color: #0f766e;
      transform: translateY(-2px);
    }

    /* Responsive Design */
    @media (max-width: 991px) {
      .list-image-container {
        min-height: 70px;
      }
      
      .product-title-mini {
        font-size: 0.9rem;
      }
      
      .current-price-mini {
        font-size: 1rem;
      }
    }

    @media (max-width: 767px) {
      .list-image-container {
        min-height: 60px;
      }
      
      .current-price-mini {
        font-size: 0.95rem;
      }
      
      .btn-micro {
        width: 28px;
        height: 24px;
        font-size: 11px;
      }
      
      .product-title-mini {
        font-size: 0.85rem;
      }
    }

    @media (max-width: 575px) {
      .list-image-container {
        min-height: 50px;
      }
      
      .product-list-item {
        margin-bottom: 8px !important;
        min-height: 65px;
      }
      
      .current-price-mini {
        font-size: 0.9rem;
      }
      
      .original-price-mini {
        font-size: 0.75rem;
      }
      
      .product-title-mini {
        font-size: 0.8rem;
      }
      
      .stars-mini {
        font-size: 12px;
      }
      
      .rating-text-mini {
        font-size: 10px;
      }
      
      .category-badge-mini {
        font-size: 9px;
        padding: 2px 4px;
      }
      
      .btn-micro {
        width: 24px;
        height: 20px;
        font-size: 10px;
      }
    }
  `]
})
export class ProductListComponent {
  @Input() products: Product[] = [];
  Math = Math;

  onImageError(event: any) {
    const placeholder = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIwIiBoZWlnaHQ9IjEyMCIgdmlld0JveD0iMCAwIDEyMCAxMjAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIxMjAiIGhlaWdodD0iMTIwIiBmaWxsPSIjRjhGOUZBIi8+CjxwYXRoIGQ9Ik02MCA0MEw0OCA1Mkw3MiA1MloiIGZpbGw9IiM2OTc1OEIiLz4KPGNpcmNsZSBjeD0iNDUiIGN5PSIzNSIgcj0iNSIgZmlsbD0iIzY5NzU4QiIvPgo8dGV4dCB4PSI2MCIgeT0iNzUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxMCIgZmlsbD0iIzY5NzU4QiI+R8O2cnNlbCBZb2s8L3RleHQ+Cjwvc3ZnPgo=';
    event.target.src = placeholder;
    event.target.style.objectFit = 'contain';
    event.target.style.background = '#f8f9fa';
    event.target.style.border = '1px dashed #cbd5e1';
  }

  getStars(rating: number): number[] {
    const stars = Math.floor(rating);
    return Array(Math.min(stars, 5)).fill(0);
  }

  getEmptyStars(rating: number): number[] {
    const emptyStars = 5 - Math.floor(rating);
    return Array(Math.max(emptyStars, 0)).fill(0);
  }
}