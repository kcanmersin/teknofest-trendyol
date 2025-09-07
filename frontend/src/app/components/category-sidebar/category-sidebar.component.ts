import { Component, OnInit, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ProductService } from '../../services/product.service';

interface CategoryGroup {
  name: string;
  icon: string;
  color: string;
  subcategories: SubCategory[];
  isExpanded?: boolean;
}

interface SubCategory {
  name: string;
  count: number;
  isSelected?: boolean;
}

@Component({
  selector: 'app-category-sidebar',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="category-sidebar bg-white rounded-4 shadow-lg p-4" style="height: fit-content;">
      <!-- Header -->
      <div class="d-flex align-items-center justify-content-between mb-4">
        <h5 class="mb-0 fw-bold" style="color: #1e293b;">
          <i class="fas fa-filter me-2" style="color: #0f766e;"></i>Kategoriler
        </h5>
        <button *ngIf="hasActiveFilters()" 
                (click)="clearAllFilters()" 
                class="btn btn-sm btn-outline-danger">
          <i class="fas fa-times me-1"></i>Temizle
        </button>
      </div>

      <!-- Loading State -->
      <div *ngIf="isLoading" class="text-center py-3">
        <div class="spinner-border spinner-border-sm text-primary" role="status"></div>
        <small class="d-block mt-2 text-muted">Kategoriler yükleniyor...</small>
      </div>

      <!-- Categories -->
      <div *ngIf="!isLoading" class="category-groups">
        <div *ngFor="let group of categoryGroups" class="category-group mb-3">
          <!-- Group Header -->
          <div class="group-header p-3 rounded-3 mb-2 cursor-pointer" 
               [style.background]="'linear-gradient(135deg, ' + group.color + '20, ' + group.color + '10)'"
               [style.border-left]="'4px solid ' + group.color"
               (click)="toggleGroup(group)">
            <div class="d-flex align-items-center justify-content-between">
              <div class="d-flex align-items-center">
                <i [class]="group.icon + ' me-2'" [style.color]="group.color"></i>
                <span class="fw-bold" style="color: #1e293b;">{{ group.name }}</span>
                <small class="badge bg-light text-muted ms-2">{{ getGroupTotal(group) }}</small>
              </div>
              <i class="fas" 
                 [class.fa-chevron-down]="group.isExpanded"
                 [class.fa-chevron-right]="!group.isExpanded"
                 style="color: #64748b;"></i>
            </div>
          </div>

          <!-- Subcategories -->
          <div *ngIf="group.isExpanded" class="subcategories ms-3">
            <div *ngFor="let sub of group.subcategories" 
                 class="subcategory-item p-2 rounded-2 mb-1 cursor-pointer"
                 [class.selected]="sub.isSelected"
                 (click)="toggleSubcategory(group, sub)">
              <div class="d-flex align-items-center justify-content-between">
                <div class="d-flex align-items-center">
                  <div class="selection-indicator me-2" 
                       [class.selected]="sub.isSelected"></div>
                  <span class="small" 
                        [style.color]="sub.isSelected ? group.color : '#475569'">
                    {{ sub.name }}
                  </span>
                </div>
                <small class="text-muted">{{ formatCount(sub.count) }}</small>
              </div>
            </div>
            
            <!-- Show More Button -->
            <div *ngIf="group.subcategories.length > 8" class="text-center mt-2">
              <button class="btn btn-sm btn-link" style="color: #0f766e; font-size: 12px;">
                <i class="fas fa-plus me-1"></i>Daha fazla göster
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Active Filters -->
      <div *ngIf="hasActiveFilters()" class="active-filters mt-4 pt-3 border-top">
        <h6 class="small fw-bold text-muted mb-2">AKTİF FİLTRELER</h6>
        <div class="d-flex flex-wrap gap-1">
          <span *ngFor="let filter of getActiveFilters()" 
                class="badge rounded-pill px-2 py-1 cursor-pointer"
                style="background: linear-gradient(45deg, #0f766e, #059669); color: white; font-size: 10px;"
                (click)="removeFilter(filter)">
            {{ filter.name }}
            <i class="fas fa-times ms-1"></i>
          </span>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .category-sidebar {
      max-height: calc(100vh - 40px);
      overflow-y: auto;
      position: sticky;
      top: 20px;
    }

    .cursor-pointer {
      cursor: pointer;
    }

    .group-header:hover {
      transform: translateX(2px);
      transition: all 0.2s ease;
    }

    .subcategory-item {
      transition: all 0.2s ease;
    }

    .subcategory-item:hover {
      background: #f1f5f9 !important;
      transform: translateX(2px);
    }

    .subcategory-item.selected {
      background: linear-gradient(135deg, #0f766e20, #05966920) !important;
      border-left: 3px solid #0f766e;
    }

    .selection-indicator {
      width: 12px;
      height: 12px;
      border: 2px solid #cbd5e1;
      border-radius: 50%;
      transition: all 0.2s ease;
    }

    .selection-indicator.selected {
      background: #0f766e;
      border-color: #0f766e;
      position: relative;
    }

    .selection-indicator.selected::after {
      content: '✓';
      position: absolute;
      top: -2px;
      left: 1px;
      color: white;
      font-size: 8px;
      font-weight: bold;
    }

    .category-sidebar::-webkit-scrollbar {
      width: 4px;
    }

    .category-sidebar::-webkit-scrollbar-track {
      background: #f1f1f1;
      border-radius: 10px;
    }

    .category-sidebar::-webkit-scrollbar-thumb {
      background: linear-gradient(45deg, #0f766e, #059669);
      border-radius: 10px;
    }
  `]
})
export class CategorySidebarComponent implements OnInit {
  @Output() categoryFilter = new EventEmitter<string[]>();
  
  categoryGroups: CategoryGroup[] = [];
  isLoading = false;

  constructor(private productService: ProductService) {}

  ngOnInit() {
    this.loadCategories();
  }

  loadCategories() {
    this.isLoading = true;
    
    // Şimdilik normal categories endpoint'ini kullan
    this.productService.getCategories().subscribe({
      next: (data) => {
        this.processCategoryData(data);
        this.isLoading = false;
      },
      error: (error) => {
        console.error('Categories loading error:', error);
        this.isLoading = false;
      }
    });
  }

  processCategoryData(data: any) {
    // Manuel gruplama yap
    this.categoryGroups = [
      {
        name: 'Giyim & Moda',
        icon: 'fas fa-tshirt',
        color: '#0f766e',
        isExpanded: true,
        subcategories: this.getSubcategoriesForLevel1(data.level2_categories, ['Giyim']).slice(0, 15)
      },
      {
        name: 'Ayakkabı',
        icon: 'fas fa-shoe-prints', 
        color: '#7c3aed',
        isExpanded: false,
        subcategories: this.getSubcategoriesForLevel1(data.level2_categories, ['Ayakkabı']).slice(0, 12)
      },
      {
        name: 'Aksesuar & Takı',
        icon: 'fas fa-gem',
        color: '#dc2626',
        isExpanded: false,
        subcategories: this.getSubcategoriesForLevel1(data.level2_categories, ['Aksesuar']).slice(0, 12)
      },
      {
        name: 'Ev & Yaşam',
        icon: 'fas fa-home',
        color: '#059669',
        isExpanded: false,
        subcategories: this.getSubcategoriesForLevel1(data.level2_categories, [
          'Ev & Mobilya', 'Banyo Yapı & Hırdavat', 'Bahçe & Elektrikli El Aletleri'
        ]).slice(0, 10)
      },
      {
        name: 'Kozmetik & Bakım',
        icon: 'fas fa-spa',
        color: '#ec4899',
        isExpanded: false,
        subcategories: this.getSubcategoriesForLevel1(data.level2_categories, ['Kozmetik & Kişisel Bakım']).slice(0, 8)
      },
      {
        name: 'Spor & Eğlence',
        icon: 'fas fa-dumbbell',
        color: '#f59e0b',
        isExpanded: false,
        subcategories: this.getSubcategoriesForLevel1(data.level2_categories, [
          'Spor & Outdoor', 'Hobi & Eğlence'
        ]).slice(0, 8)
      },
      {
        name: 'Anne & Bebek',
        icon: 'fas fa-baby',
        color: '#06b6d4',
        isExpanded: false,
        subcategories: this.getSubcategoriesForLevel1(data.level2_categories, ['Anne & Bebek & Çocuk']).slice(0, 6)
      },
      {
        name: 'Teknoloji & Diğer',
        icon: 'fas fa-laptop',
        color: '#6366f1',
        isExpanded: false,
        subcategories: this.getSubcategoriesForLevel1(data.level2_categories, [
          'Elektronik', 'Otomobil & Motosiklet', 'Kırtasiye & Ofis Malzemeleri', 
          'Kitap', 'Süpermarket', 'Ek Hizmetler'
        ]).slice(0, 10)
      }
    ];
  }

  getSubcategoriesForLevel1(level2Categories: any[], level1Names: string[]): SubCategory[] {
    return level2Categories
      .filter(cat => level1Names.includes(cat.level1_category_name))
      .map(cat => ({
        name: cat.level2_category_name,
        count: cat.product_count,
        isSelected: false
      }))
      .sort((a, b) => b.count - a.count);
  }

  toggleGroup(group: CategoryGroup) {
    group.isExpanded = !group.isExpanded;
  }

  toggleSubcategory(group: CategoryGroup, subcategory: SubCategory) {
    subcategory.isSelected = !subcategory.isSelected;
    this.emitFilterChange();
  }

  getGroupTotal(group: CategoryGroup): string {
    const total = group.subcategories.reduce((sum, sub) => sum + sub.count, 0);
    return this.formatCount(total);
  }

  formatCount(count: number): string {
    if (count >= 1000000) {
      return (count / 1000000).toFixed(1) + 'M';
    } else if (count >= 1000) {
      return (count / 1000).toFixed(0) + 'K';
    }
    return count.toString();
  }

  hasActiveFilters(): boolean {
    return this.categoryGroups.some(group => 
      group.subcategories.some(sub => sub.isSelected)
    );
  }

  getActiveFilters(): any[] {
    const filters: any[] = [];
    this.categoryGroups.forEach(group => {
      group.subcategories.forEach(sub => {
        if (sub.isSelected) {
          filters.push({
            name: sub.name,
            group: group.name,
            subcategory: sub
          });
        }
      });
    });
    return filters;
  }

  removeFilter(filter: any) {
    filter.subcategory.isSelected = false;
    this.emitFilterChange();
  }

  clearAllFilters() {
    this.categoryGroups.forEach(group => {
      group.subcategories.forEach(sub => {
        sub.isSelected = false;
      });
    });
    this.emitFilterChange();
  }

  emitFilterChange() {
    const selectedCategories = this.getActiveFilters().map(f => f.name);
    this.categoryFilter.emit(selectedCategories);
  }
}