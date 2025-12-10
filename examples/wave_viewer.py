import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.colors import Normalize

class QuantumScene:
    def __init__(self, x_range=(-10, 10), y_range=(-10, 10), resolution=100):
        """
        Inizializza la griglia spaziale 2D.
        """
        self.x = np.linspace(x_range[0], x_range[1], resolution)
        self.y = np.linspace(y_range[0], y_range[1], resolution)
        self.X, self.Y = np.meshgrid(self.x, self.y)
        # Inizializza la funzione d'onda come griglia di zeri (complessa)
        self.psi = np.zeros_like(self.X, dtype=np.complex128)

    def add_plane_wave(self, kx, ky, amplitude=1.0):
        """
        Aggiunge un'onda piana: Psi = A * exp(i(kx*x + ky*y))
        Utile per simulare particelle libere con momento definito.
        """
        wave = amplitude * np.exp(1j * (kx * self.X + ky * self.Y))
        self.psi += wave

    def add_gaussian_packet(self, x0, y0, sigma, kx=0, ky=0, amplitude=1.0):
        """
        Aggiunge un pacchetto d'onda Gaussiano.
        Rappresenta una particella localizzata (principio di indeterminazione).
        """
        # Parte spaziale (busta gaussiana)
        spatial_envelope = np.exp(-((self.X - x0)**2 + (self.Y - y0)**2) / (2 * sigma**2))
        # Parte del momento (onda piana)
        momentum_part = np.exp(1j * (kx * self.X + ky * self.Y))
        
        packet = amplitude * spatial_envelope * momentum_part
        self.psi += packet

    def add_harmonic_oscillator(self, n, m, alpha=1.0):
        """
        Aggiunge uno stato dell'oscillatore armonico quantistico 2D (Hermite polynomials).
        Fondamentale per la computazione quantistica (modi discreti).
        n, m: numeri quantici lungo x e y.
        """
        from numpy.polynomial.hermite import hermval
        
        # Coefficienti per il polinomio di Hermite (seleziona l'n-esimo e m-esimo)
        c_n = [0] * n + [1]
        c_m = [0] * m + [1]
        
        Hx = hermval(np.sqrt(alpha) * self.X, c_n)
        Hy = hermval(np.sqrt(alpha) * self.Y, c_m)
        
        # Funzione d'onda normalizzata (forma base)
        psi_nm = (Hx * Hy * np.exp(-alpha * (self.X**2 + self.Y**2) / 2))
        self.psi += psi_nm * (1.0 + 0j) # Converti in complesso

    def normalize(self):
        """Normalizza la funzione d'onda totale affinché la somma delle probabilità sia 1."""
        norm_factor = np.sqrt(np.sum(np.abs(self.psi)**2))
        if norm_factor > 0:
            self.psi /= norm_factor

    def render_3d(self, title="Funzione d'Onda Quantistica"):
        """
        Visualizza la funzione d'onda in 3D.
        Z-axis: Densità di Probabilità |Psi|^2
        Colore: Fase (Argomento di Psi)
        """
        fig, ax = plt.subplots(subplot_kw={"projection": "3d"}, figsize=(12, 8))
        
        # Calcolo grandezze fisiche
        probability_density = np.abs(self.psi)**2
        phase = np.angle(self.psi)
        
        # Mappatura della fase su una colormap (hsv è ciclico, perfetto per le fasi)
        # Normalizziamo la fase da -pi a pi -> 0 a 1
        norm = Normalize(vmin=-np.pi, vmax=np.pi)
        colors = cm.hsv(norm(phase))
        
        # Plot della superficie
        surf = ax.plot_surface(self.X, self.Y, probability_density, 
                               facecolors=colors, 
                               rstride=1, cstride=1, 
                               linewidth=0, antialiased=True, shade=False)
        
        # Setup grafico
        ax.set_title(title, fontsize=15)
        ax.set_xlabel('X (Posizione)')
        ax.set_ylabel('Y (Posizione)')
        ax.set_zlabel('Probabilità $|\\psi|^2$')
        
        # Aggiunta colorbar per la fase
        m = cm.ScalarMappable(cmap=cm.hsv, norm=norm)
        m.set_array([])
        cbar = plt.colorbar(m, ax=ax, shrink=0.5, aspect=5)
        cbar.set_label('Fase (Interferenza)', rotation=270, labelpad=15)
        
        plt.show()

# --- ESEMPIO DI UTILIZZO ---

if __name__ == "__main__":
    
    # 1. Creazione della scena
    qc = QuantumScene(resolution=100)
    
    # SCENARIO A: Interferenza di due fenditure (Simulata con due Gaussiane)
    # Aggiungiamo due pacchetti d'onda che si muovono uno verso l'altro
    print("Generazione scenario: Interferenza Quantistica...")
    
    # Pacchetto 1 (Sinistra)
    qc.add_gaussian_packet(x0=-3, y0=0, sigma=1.5, kx=2.0, amplitude=1.0)
    
    # Pacchetto 2 (Destra) - Aggiungendo questo vediamo l'interferenza
    qc.add_gaussian_packet(x0=3, y0=0, sigma=1.5, kx=-2.0, amplitude=1.0)
    
    # SCENARIO B: De-commenta sotto per vedere un Oscillatore Armonico (Stato eccitato)
    # qc = QuantumScene()
    # qc.add_harmonic_oscillator(n=2, m=2, alpha=0.5)

    # Rendering
    qc.normalize()
    qc.render_3d("Interferenza di due Pacchetti d'Onda (Colore = Fase)")