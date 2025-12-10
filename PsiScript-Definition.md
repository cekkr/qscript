# PsiScript v1.0 - Technical Reference Manual

## 1\. Overview

PsiScript is a high-level, geometry-oriented quantum description language. It abstracts the underlying Hilbert space manipulations into four geometric primitives: `Superpose`, `Phase`, `Reflect`, and `Flip`.

**Core Philosophy:** The programmer defines **constraints** and **geometric transformations** on the state vector. The compiler (Transpiler) handles the translation into reversible quantum gates, ancilla management, and uncomputation steps.

-----

## 2\. Primitives & Synthesis

### 2.1 `Superpose(Target)`

Distributes probability amplitude equally across the target subspace.

  * **Syntax:** `Register.Superpose(ALL | IndexList)`
  * **Physical Meaning:** Creation of coherence.
  * **Circuit Synthesis:**
      * Maps directly to **Hadamard (H)** gates applied to each qubit in the target list.
      * *Depth:* O(1) (Parallel execution).

-----

### 2.2 `Phase(Angle, Predicate)`

Rotates the phase of the quantum states that satisfy the `Predicate` condition. This is the primary method for injecting logic/data into the system.

  * **Syntax:** `Register.Phase(PI, WHERE Q[0] == Q[1])`

  * **Physical Meaning:** Multiplies the amplitude of matching states by $e^{i\theta}$. If Angle is $\pi$, it multiplies by $-1$ (Phase Flip).

  * **Circuit Synthesis (The "Oracle" Construction):**
    The compiler synthesizes a **Boolean Oracle** using the *Compute-Phase-Uncompute* pattern.

    **Example: `WHERE Q[0] == Q[1]`**
    To implement this, the compiler generates the following circuit block:

    1.  **Allocate Ancilla:** A temporary qubit `A0` is initialized to $|-\rangle$ (for phase kickback) or used with a Z-gate.
    2.  **Compute Logic (XOR):**
          * The condition "Equal" is equivalent to `NOT(Q[0] XOR Q[1])`.
          * *Gate:* `CNOT(Q[0], A0)` followed by `CNOT(Q[1], A0)`.
          * Now `A0` holds `Q[0] XOR Q[1]`.
    3.  **Targeting "Equality":** Since we want equality (XOR result 0), we apply `X(A0)` to flip the logic. Now `A0` is 1 if they are equal.
    4.  **Inject Phase (The Kickback):**
          * *Gate:* Apply a **Phase Gate (Z)** or Controlled-Z on `A0`. This transfers the phase to the computational basis states involved.
    5.  **Uncompute (Clean-up):**
          * **CRITICAL STEP:** Quantum computing must be reversible. We cannot leave `A0` dirty, or it remains entangled with the system, destroying interference.
          * *Gate:* Apply `X(A0)`, then `CNOT(Q[1], A0)`, then `CNOT(Q[0], A0)` (The exact reverse of step 2 and 3).
    6.  **Release Ancilla:** `A0` is now back to $|0\rangle$ and disconnected.

-----

### 2.3 `Reflect(Axis)`

Performs an inversion of amplitudes around a specified geometric axis (typically the Mean).

  * **Syntax:** `Register.Reflect(Axis.MEAN)`
  * **Physical Meaning:** Amplification of probability for states marked with a negative phase.
  * **Circuit Synthesis:**
    This compiles into the standard "Diffusion Operator" circuit:
    1.  Apply **Hadamard (H)** to all qubits.
    2.  Apply **NOT (X)** to all qubits.
    3.  Apply a **Multi-Controlled Z (MCZ)** gate across all qubits.
    4.  Apply **NOT (X)** to all qubits.
    5.  Apply **Hadamard (H)** to all qubits.
    <!-- end list -->
      * *Note:* The MCZ gate often requires decomposition into smaller Toffoli gates and linear-depth ladders of ancilla qubits depending on connectivity.

-----

### 2.4 `Flip(Target, Condition)`

Permutes states (swaps amplitudes) between basis vectors.

  * **Syntax:** `Register.Flip(Q[1], IF Q[0] == 1)`
  * **Physical Meaning:** Conditional logic / Entanglement creation.
  * **Circuit Synthesis:**
      * **Simple:** `IF Q[0] == 1` maps directly to a **CNOT** gate (Control: Q[0], Target: Q[1]).
      * **Complex:** `IF (Q[0] == 1 AND Q[2] == 0)`
          * The compiler inserts `X(Q[2])` (to satisfy the '0' condition).
          * Applies a **Toffoli (CCNOT)** or Multi-Controlled X gate.
          * Inserts `X(Q[2])` again to restore the state.

-----

## 3\. Practical Example: The "Equality Check"

Let's look at the synthesized circuit for the user command:
**`Phase(PI, WHERE Q[0] == Q[1])`**

### The PsiScript View (Programmer's Mind):

> "Mark the states where the first two qubits are identical (00 and 11) by flipping their phase."

### The Transpiled Circuit (Hardware View):

This is what the `.psi` file compiles to in OpenQASM/Circuit language:

```assembly
// 1. Prepare Ancilla (A0) in state |-> for Phase Kickback
reg q[2]    // System
reg a[1]    // Ancilla
x a[0];
h a[0];

// 2. COMPUTE: Calculate XOR (Q0 != Q1) into Ancilla
cx q[0], a[0];
cx q[1], a[0];

// 3. LOGIC ADAPTATION: We want Q0 == Q1, so we flip the XOR result
x a[0];

// 4. PHASE INJECTION: The Ancilla is now 1 only if Q0 == Q1.
// Because Ancilla is in |-> state, this X gate actually
// injected a global phase of -1 to the entangled system *IF* the condition met.
// (Alternative: If Ancilla was |0>, we would use a CZ gate here).

// 5. UNCOMPUTE: Reverse everything to clean Ancilla
x a[0];
cx q[1], a[0];
cx q[0], a[0];

// 6. Restore Ancilla (Optional, if needed for reuse)
h a[0];
x a[0];
```

-----

## 4\. Hardware Constraints & Optimization

The compiler includes an **Optimizer** stage. Since physical qubits have limited connectivity (e.g., Qubit 0 might only be connected to Qubit 1, not Qubit 2), the PsiScript synthesis engine automatically injects **SWAP networks**.

  * **Constraint:** If you write `WHERE Q[0] == Q[10]`, and they are physically far apart.
  * **Synthesis:** The compiler generates a "bucket brigade" of SWAP gates to bring the information of Q[0] adjacent to Q[10], performs the logic, and SWAPs them back.
  * **Warning:** This drastically increases circuit depth and decoherence risk. PsiScript IDE will highlight this line in yellow ("High Decoherence Cost").

