/**
 * Pilha de comandos imutáveis com undo/redo e teto de histórico.
 * Capacidade padrão 100; o critério de aceite pede ≥ 20 operações.
 */
export class CommandStack<T> {
  private undoStack: T[] = [];
  private redoStack: T[] = [];
  private readonly maxSize: number;

  constructor(maxSize = 100) {
    if (maxSize < 1) {
      throw new Error('CommandStack.maxSize deve ser ≥ 1.');
    }
    this.maxSize = maxSize;
  }

  get canUndo(): boolean {
    return this.undoStack.length > 0;
  }

  get canRedo(): boolean {
    return this.redoStack.length > 0;
  }

  get undoCount(): number {
    return this.undoStack.length;
  }

  get redoCount(): number {
    return this.redoStack.length;
  }

  get undoItems(): readonly T[] {
    return this.undoStack;
  }

  get redoItems(): readonly T[] {
    return this.redoStack;
  }

  push(command: T): void {
    this.undoStack.push(command);
    if (this.undoStack.length > this.maxSize) {
      this.undoStack.shift();
    }
    this.redoStack = [];
  }

  undo(): T | undefined {
    const command = this.undoStack.pop();
    if (command === undefined) {
      return undefined;
    }
    this.redoStack.push(command);
    return command;
  }

  redo(): T | undefined {
    const command = this.redoStack.pop();
    if (command === undefined) {
      return undefined;
    }
    this.undoStack.push(command);
    return command;
  }

  clear(): void {
    this.undoStack = [];
    this.redoStack = [];
  }
}
