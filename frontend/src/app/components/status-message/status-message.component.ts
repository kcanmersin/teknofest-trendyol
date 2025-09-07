import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

export type StatusType = 'success' | 'error' | 'loading';

@Component({
  selector: 'app-status-message',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div *ngIf="visible" 
         [ngClass]="{
           'alert-success': type === 'success',
           'alert-danger': type === 'error',
           'alert-info': type === 'loading'
         }"
         class="alert alert-dismissible my-4 fw-medium">
      {{ message }}
    </div>
  `
})
export class StatusMessageComponent {
  @Input() message = '';
  @Input() type: StatusType = 'success';
  @Input() visible = false;
}