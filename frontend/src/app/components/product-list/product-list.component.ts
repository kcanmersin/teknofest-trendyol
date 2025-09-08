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
           class="product-list-item bg-white rounded-3 shadow-sm mb-3 p-4"
           [style.animation-delay.ms]="i * 30"
           style="animation: fadeInUp 0.4s ease forwards; opacity: 0;">
        
        <div class="row align-items-center">
          <!-- Product Image -->
          <div class="col-12 col-sm-3 col-md-2">
            <div class="position-relative" style="height: 120px;">
              <img [src]="product.image_url" 
                   [alt]="product.content_title"
                   class="img-fluid rounded-2 w-100 h-100"
                   style="object-fit: cover;"
                   (error)="onImageError($event)">
              
              <!-- Discount Badge -->
              <div *ngIf="product.discount_percentage" 
                   class="position-absolute top-0 start-0 m-1">
                <span class="badge bg-danger text-white px-2 py-1 rounded-pill" style="font-size: 10px;">
                  {{ product.discount_percentage }}% İndirim
                </span>
              </div>
            </div>
          </div>

          <!-- Product Info -->
          <div class="col-12 col-sm-6 col-md-7">
            <div class="h-100 d-flex flex-column justify-content-between">
              <!-- Categories -->
              <div class="mb-2">
                <div class="d-flex gap-1 flex-wrap">
                  <span class="badge text-white rounded-pill px-2 py-1" 
                        style="background: linear-gradient(45deg, #0f766e, #059669); font-size: 9px;">
                    {{ product.level1_category_name }}
                  </span>
                  <span class="badge bg-secondary text-white rounded-pill px-2 py-1" 
                        style="font-size: 8px;">
                    {{ product.level2_category_name }}
                  </span>
                </div>
              </div>

              <!-- Title -->
              <h6 class="mb-2 fw-bold" style="color: #1e293b; line-height: 1.3;">
                {{ product.content_title }}
              </h6>

              <!-- Details -->
              <div class="small text-muted mb-2">
                <div class="row g-2">
                  <div class="col-6">
                    <span class="text-muted">ID:</span> 
                    <code style="font-size: 10px;">{{ product.content_id_hashed.substring(0, 8) }}...</code>
                  </div>
                  <div class="col-6">
                    <span class="text-muted">Satıcı:</span> 
                    <span class="badge bg-info text-white">{{ product.merchant_count || 0 }}</span>
                  </div>
                </div>
              </div>

              <!-- Rating -->
              <div class="d-flex align-items-center gap-2">
                <div class="text-warning">
                  <i class="fas fa-star" *ngFor="let star of getStars(product.content_rate_avg || 0)"></i>
                  <i class="far fa-star" *ngFor="let star of getEmptyStars(product.content_rate_avg || 0)"></i>
                </div>
                <small class="text-muted">({{ product.content_review_count }} yorum)</small>
              </div>
            </div>
          </div>

          <!-- Price & Actions -->
          <div class="col-12 col-sm-3 col-md-3">
            <div class="text-sm-end mt-3 mt-sm-0">
              <!-- Price -->
              <div class="mb-3">
                <div class="text-success fw-bold fs-5">₺{{ product.discounted_price | number:'1.2-2' }}</div>
                <div *ngIf="product.original_price !== product.discounted_price" 
                     class="text-muted text-decoration-line-through small">
                  ₺{{ product.original_price | number:'1.2-2' }}
                </div>
              </div>

              <!-- Action Buttons -->
              <div class="d-flex flex-column gap-2">
                <button class="btn btn-outline-primary btn-sm rounded-pill">
                  <i class="fas fa-eye me-1"></i>Detay
                </button>
                <button class="btn btn-primary btn-sm rounded-pill" 
                        style="background: linear-gradient(45deg, #0f766e, #059669); border: none;">
                  <i class="fas fa-external-link-alt me-1"></i>Git
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .product-list-item {
      transition: all 0.3s ease;
      border: 1px solid #e2e8f0;
    }

    .product-list-item:hover {
      transform: translateX(5px);
      box-shadow: 0 10px 25px rgba(0,0,0,0.1) !important;
      border-color: #0f766e;
    }

    @media (max-width: 576px) {
      .product-list-item .col-12:not(:last-child) {
        margin-bottom: 15px;
      }
      
      .product-list-item .text-sm-end {
        text-align: center !important;
      }
      
      .product-list-item .d-flex.flex-column {
        flex-direction: row !important;
        justify-content: center;
        gap: 10px;
      }
    }
  `]
})
export class ProductListComponent {
  @Input() products: Product[] = [];

  onImageError(event: any) {
    event.target.src = 'https://via.placeholder.com/120x120/f8f9fa/6c757d?text=Görsel+Yok';
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