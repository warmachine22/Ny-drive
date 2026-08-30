import { actionForKey, DrivingInputState } from './actions';

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }

  return (
    target.isContentEditable ||
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement
  );
}

export class KeyboardInput {
  readonly state = new DrivingInputState();

  private attached = false;

  private readonly onKeyDown = (event: KeyboardEvent): void => {
    if (isEditableTarget(event.target)) return;
    const action = actionForKey(event.code);
    if (!action) return;
    event.preventDefault();
    this.state.set(action, true);
  };

  private readonly onKeyUp = (event: KeyboardEvent): void => {
    if (isEditableTarget(event.target)) return;
    const action = actionForKey(event.code);
    if (!action) return;
    event.preventDefault();
    this.state.set(action, false);
  };

  private readonly onBlur = (): void => {
    this.state.clear();
  };

  attach(target: Window = window): void {
    if (this.attached) return;
    target.addEventListener('keydown', this.onKeyDown);
    target.addEventListener('keyup', this.onKeyUp);
    target.addEventListener('blur', this.onBlur);
    this.attached = true;
  }

  detach(target: Window = window): void {
    if (!this.attached) return;
    target.removeEventListener('keydown', this.onKeyDown);
    target.removeEventListener('keyup', this.onKeyUp);
    target.removeEventListener('blur', this.onBlur);
    this.state.clear();
    this.attached = false;
  }
}
