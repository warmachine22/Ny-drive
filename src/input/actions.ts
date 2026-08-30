export const drivingActions = [
  'steerLeft',
  'steerRight',
  'throttle',
  'brakeReverse',
  'handbrake',
  'reset',
] as const;

export type DrivingAction = (typeof drivingActions)[number];

export interface DrivingInputSnapshot {
  steer: number;
  throttle: number;
  brakeReverse: number;
  handbrake: boolean;
  reset: boolean;
}

const KEY_TO_ACTION: Readonly<Record<string, DrivingAction>> = {
  ArrowLeft: 'steerLeft',
  KeyA: 'steerLeft',
  ArrowRight: 'steerRight',
  KeyD: 'steerRight',
  ArrowUp: 'throttle',
  KeyW: 'throttle',
  ArrowDown: 'brakeReverse',
  KeyS: 'brakeReverse',
  Space: 'handbrake',
  KeyR: 'reset',
};

export function actionForKey(code: string): DrivingAction | undefined {
  return KEY_TO_ACTION[code];
}

export class DrivingInputState {
  private readonly active = new Set<DrivingAction>();

  set(action: DrivingAction, pressed: boolean): void {
    if (pressed) {
      this.active.add(action);
    } else {
      this.active.delete(action);
    }
  }

  clear(): void {
    this.active.clear();
  }

  snapshot(): DrivingInputSnapshot {
    const left = this.active.has('steerLeft') ? 1 : 0;
    const right = this.active.has('steerRight') ? 1 : 0;

    return {
      steer: right - left,
      throttle: this.active.has('throttle') ? 1 : 0,
      brakeReverse: this.active.has('brakeReverse') ? 1 : 0,
      handbrake: this.active.has('handbrake'),
      reset: this.active.has('reset'),
    };
  }
}
