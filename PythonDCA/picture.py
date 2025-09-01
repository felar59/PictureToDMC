from PIL import Image, ImageFilter
import numpy as np
from sklearn.cluster import KMeans

class Picture:
    def __init__(self, picture64, colorsAmount=9):
        im = picture64.convert("RGBA")
        alpha = np.array(im.getchannel("A"))
        rgb = np.array(im.convert("RGB"))

        # On garde seulement les pixels visibles
        mask = alpha > 0
        pixels = rgb[mask]

        # KMeans pour trouver les couleurs dominantes
        kmeans = KMeans(n_clusters=colorsAmount, random_state=42).fit(pixels)
        palette = np.array(kmeans.cluster_centers_, dtype=np.uint8)

        # Remappe chaque pixel à sa couleur dominante
        labels = kmeans.predict(rgb.reshape(-1, 3))
        new_rgb = palette[labels].reshape(rgb.shape)

        # On remet le canal alpha d'origine
        new_image = Image.fromarray(np.dstack((new_rgb, alpha)), "RGBA")

        self.im = new_image
        self.pix = self.im.load()
        self.width, self.height = self.im.size

    def get_pix(self, x, y):
        return self.pix[x, y]

    def get_size(self):
        return (self.width, self.height)
