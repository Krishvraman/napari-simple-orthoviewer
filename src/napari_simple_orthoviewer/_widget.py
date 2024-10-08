import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from matplotlib.colors import ListedColormap
import tifffile
from napari.utils.colormaps import label_colormap
from qtpy.QtWidgets import QWidget, QVBoxLayout, QComboBox, QPushButton, QLabel
import napari
import matplotlib.colors as mcolors

class Ortho_control(QWidget):
    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari_viewer

        # Set up the layout
        layout = QVBoxLayout()

        # Image layers dropdown
        self.image_layer_label = QLabel("Image", self)
        layout.addWidget(self.image_layer_label)
        self.image_layer_dropdown = QComboBox(self)
        self.update_image_layers()
        layout.addWidget(self.image_layer_dropdown)

        # Label layers dropdown
        self.label_layer_label = QLabel("Label", self)
        layout.addWidget(self.label_layer_label)
        self.label_layer_dropdown = QComboBox(self)
        self.update_label_layers()
        layout.addWidget(self.label_layer_dropdown)

        # Button
        self.button = QPushButton("Execute Orthogonal Views", self)
        self.button.clicked.connect(self.run_function)
        layout.addWidget(self.button)

        self.setLayout(layout)
        self.volume = None
        self.label = None

        # Connect the layer update to the viewer
        self.viewer.layers.events.inserted.connect(self.update_image_layers)
        self.viewer.layers.events.inserted.connect(self.update_label_layers)
        self.viewer.layers.events.removed.connect(self.update_image_layers)
        self.viewer.layers.events.removed.connect(self.update_label_layers)

    def update_image_layers(self, event=None):
        self.image_layer_dropdown.clear()
        image_layers = [layer.name for layer in self.viewer.layers if isinstance(layer, napari.layers.Image)]
        self.image_layer_dropdown.addItems(image_layers)

    def update_label_layers(self, event=None):
        self.label_layer_dropdown.clear()
        label_layers = [layer.name for layer in self.viewer.layers if isinstance(layer, napari.layers.Labels)]
        self.label_layer_dropdown.addItems(label_layers)

    def run_function(self):
        selected_image_name = self.image_layer_dropdown.currentText()
        selected_label_name = self.label_layer_dropdown.currentText()
        self.volume = None
        self.label = None

        if selected_image_name:
            layer = self.viewer.layers[selected_image_name]
            self.volume = layer.data


        if selected_label_name:
            layer = self.viewer.layers[selected_label_name]
            self.label = layer.data

        if self.volume is not None:
            ortho_viewer = OrthogonalViewer(self.volume,label = self.label)



class OrthogonalViewer:
    def __init__(self, volume, label=None):
        self.volume = volume
        self.label = label
        self.shape = volume.shape
        self.slices = [self.shape[0] // 2, self.shape[1] // 2, self.shape[2] // 2]
        plt.style.use('dark_background')
        self.fig, self.axes = plt.subplots(1, 3, figsize=(15, 5))

        # Display initial views with labels if available
        self.im_axial = self.axes[0].imshow(self.volume[self.slices[0], :, :], cmap='gray', interpolation='none')
        self.im_coronal = self.axes[1].imshow(self.volume[:, self.slices[1], :], cmap='gray', interpolation='none')
        self.im_sagittal = self.axes[2].imshow(self.volume[:, :, self.slices[2]], cmap='gray', interpolation='none')


        # Get the default 'glasbey' colormap used for label layers
        default_colormap = label_colormap()

        # Extract the colors from the CyclicLabelColormap object
        # This will give us a numpy array of shape (n_labels, 4), where the last dimension is RGBA
        cmap_colors = default_colormap.colors

        # Create a ListedColormap for Matplotlib using only the non-background colors (ignoring the first color)
        matplotlib_cmap = ListedColormap(cmap_colors)

        self.custcmap = matplotlib_cmap

        if self.label is not None:
            self.norm = mcolors.Normalize(vmin=self.label.min(), vmax=self.label.max())
            self.label_axial = self.axes[0].imshow(self.label[self.slices[0], :, :], cmap=self.custcmap,norm=self.norm, alpha=0.5, interpolation='none')
            self.label_coronal = self.axes[1].imshow(self.label[:, self.slices[1], :], cmap=self.custcmap, norm=self.norm ,alpha=0.5, interpolation='none')
            self.label_sagittal = self.axes[2].imshow(self.label[:, :, self.slices[2]], cmap=self.custcmap, norm=self.norm,alpha=0.5, interpolation='none')

        # Set titles
        self.axes[0].set_title('XY')
        self.axes[1].set_title('YZ')
        self.axes[2].set_title('XZ')

        # Add sliders for each view
        axcolor = 'lightgoldenrodyellow'
        ax_slider_axial = plt.axes([0.1, 0.02, 0.2, 0.03], facecolor=axcolor)
        ax_slider_coronal = plt.axes([0.4, 0.02, 0.2, 0.03], facecolor=axcolor)
        ax_slider_sagittal = plt.axes([0.7, 0.02, 0.2, 0.03], facecolor=axcolor)

        self.slider_axial = Slider(ax_slider_axial, 'Axial Slice', 0, self.shape[0] - 1, valinit=self.slices[0], valstep=1)
        self.slider_coronal = Slider(ax_slider_coronal, 'Coronal Slice', 0, self.shape[1] - 1, valinit=self.slices[1], valstep=1)
        self.slider_sagittal = Slider(ax_slider_sagittal, 'Sagittal Slice', 0, self.shape[2] - 1, valinit=self.slices[2], valstep=1)

        # Connect sliders to update functions
        self.slider_axial.on_changed(self.update_axial)
        self.slider_coronal.on_changed(self.update_coronal)
        self.slider_sagittal.on_changed(self.update_sagittal)

        # Store current limits for maintaining zoom state
        self.limits = [ax.get_xlim() + ax.get_ylim() for ax in self.axes]
        self.drag_start_pos = None

        # Connect event handlers
        self.cid_scroll = self.fig.canvas.mpl_connect('scroll_event', self.on_scroll)
        self.cid_click = self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.cid_release = self.fig.canvas.mpl_connect('button_release_event', self.on_release)
        self.cid_motion = self.fig.canvas.mpl_connect('motion_notify_event', self.on_motion)

        # Display slice lines
        self.update_slice_lines()

        plt.show()

    def on_scroll(self, event):
        if event.key == 'control':  # Check if Ctrl is held down
            self.zoom(event)
        else:  # Default behavior: scroll through slices
            if event.inaxes == self.axes[0]:
                self.slices[0] = np.clip(self.slices[0] + (1 if event.button == 'up' else -1), 0, self.shape[0] - 1)
                self.slider_axial.set_val(self.slices[0])
            elif event.inaxes == self.axes[1]:
                self.slices[1] = np.clip(self.slices[1] + (1 if event.button == 'up' else -1), 0, self.shape[1] - 1)
                self.slider_coronal.set_val(self.slices[1])
            elif event.inaxes == self.axes[2]:
                self.slices[2] = np.clip(self.slices[2] + (1 if event.button == 'up' else -1), 0, self.shape[2] - 1)
                self.slider_sagittal.set_val(self.slices[2])
            self.update_views(keep_zoom=True)

    def zoom(self, event):
        base_scale = 1.2

        for i, ax in enumerate(self.axes):
            # Get the current limits
            cur_xlim = ax.get_xlim()
            cur_ylim = ax.get_ylim()

            # Determine the slice line center for zooming
            if ax == self.axes[0]:
                xdata, ydata = self.slices[2], self.slices[1]
            elif ax == self.axes[1]:
                xdata, ydata = self.slices[2], self.slices[0]
            elif ax == self.axes[2]:
                xdata, ydata = self.slices[1], self.slices[0]

            if event.button == 'up':
                scale_factor = 1 / base_scale
            elif event.button == 'down':
                scale_factor = base_scale
            else:
                scale_factor = 1

            new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
            new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor

            relx = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
            rely = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])

            ax.set_xlim([xdata - new_width * (1 - relx), xdata + new_width * relx])
            ax.set_ylim([ydata - new_height * (1 - rely), ydata + new_height * rely])

            self.limits[i] = ax.get_xlim() + ax.get_ylim()

        self.fig.canvas.draw_idle()

    def on_click(self, event):
        if event.inaxes in self.axes:
            self.drag_start_pos = (event.xdata, event.ydata)

            if event.inaxes == self.axes[0]:
                self.slices[1] = int(event.ydata)
                self.slices[2] = int(event.xdata)
            elif event.inaxes == self.axes[1]:
                self.slices[0] = int(event.ydata)
                self.slices[2] = int(event.xdata)
            elif event.inaxes == self.axes[2]:
                self.slices[0] = int(event.ydata)
                self.slices[1] = int(event.xdata)

            self.update_views(keep_zoom=True)

    def on_release(self, event):
        self.drag_start_pos = None

    def on_motion(self, event):
        if self.drag_start_pos and event.inaxes in self.axes:
            dx = self.drag_start_pos[0] - event.xdata
            dy = self.drag_start_pos[1] - event.ydata
            ax = event.inaxes

            cur_xlim = ax.get_xlim()
            cur_ylim = ax.get_ylim()

            ax.set_xlim([cur_xlim[0] + dx, cur_xlim[1] + dx])
            ax.set_ylim([cur_ylim[0] + dy, cur_ylim[1] + dy])

            # Update the limits to maintain the pan state
            for i, ax in enumerate(self.axes):
                self.limits[i] = ax.get_xlim() + ax.get_ylim()

            self.fig.canvas.draw_idle()

    def update_views(self, keep_zoom=False):
        self.im_axial.set_data(self.volume[self.slices[0], :, :])
        self.im_coronal.set_data(self.volume[:, self.slices[1], :])
        self.im_sagittal.set_data(self.volume[:, :, self.slices[2]])

        if self.label is not None:
            # Clear existing labels
            self.clear_labels()
            # Replot the labels
            self.label_axial = self.axes[0].imshow(self.label[self.slices[0], :, :], cmap=self.custcmap, norm=self.norm, alpha=0.5, interpolation='none')
            self.label_coronal = self.axes[1].imshow(self.label[:, self.slices[1], :], cmap=self.custcmap, norm=self.norm , alpha=0.5, interpolation='none')
            self.label_sagittal = self.axes[2].imshow(self.label[:, :, self.slices[2]], cmap=self.custcmap, norm=self.norm, alpha=0.5, interpolation='none')

        self.update_slice_lines()

        if keep_zoom:
            for i, ax in enumerate(self.axes):
                ax.set_xlim(self.limits[i][:2])
                ax.set_ylim(self.limits[i][2:])

        self.fig.canvas.draw_idle()

    def clear_labels(self):
        if hasattr(self, 'label_axial'):
            self.label_axial.remove()
        if hasattr(self, 'label_coronal'):
            self.label_coronal.remove()
        if hasattr(self, 'label_sagittal'):
            self.label_sagittal.remove()

    def update_slice_lines(self):
        for ax in self.axes:
            # Remove existing lines by finding them and setting their data to empty
            lines = ax.get_lines()
            for line in lines:
                line.remove()

        # Add new slice lines
        self.axes[0].axhline(self.slices[1], color='b')
        self.axes[0].axvline(self.slices[2], color='y')
        self.axes[1].axhline(self.slices[0], color='r')
        self.axes[1].axvline(self.slices[2], color='y')
        self.axes[2].axhline(self.slices[0], color='r')
        self.axes[2].axvline(self.slices[1], color='b')

    def update_axial(self, val):
        self.slices[0] = int(val)
        self.update_views(keep_zoom=True)

    def update_coronal(self, val):
        self.slices[1] = int(val)
        self.update_views(keep_zoom=True)

    def update_sagittal(self, val):
        self.slices[2] = int(val)
        self.update_views(keep_zoom=True)
