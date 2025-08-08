
import streamlit as st

import nifits.io.oifits as io
import nifits.backend as be

import numpy as np
import matplotlib.pyplot as plt

import astropy.io.fits as fits

from time import time


st.set_page_config(layout="wide")
st.header("NIView")
st.write("## The `nifits` viewer")

def trigger_rerun():
    if "z" in st.session_state:
        del st.session_state.z

def mod2cs(mod, scalor=40.):
    """
        Transforms a complex phasor into a couple color and size 
    for scatter plots
    """
    c = (np.angle(mod) + np.pi)/(2*np.pi)
    s = scalor * np.abs(mod)**2
    return c, s

file_in = st.file_uploader("Load a nifits file", type=["nifits"])
if file_in is not None:
    mynifits = io.nifits.from_nifits(file_in)

    file_tab, combiner_tab, trans_tab, collect_tab, combination = st.tabs(("File info", "Combiner", "Transmission map", "Collected light", "Combination"))

    # st.write(mynifits)
    with file_tab:
        st.write("## Extensions: ")
        exitsting_extensions = []
        for anext in io.NIFITS_EXTENSIONS:
            if hasattr(mynifits, anext.lower()):
                exitsting_extensions.append(anext)
                with st.expander(anext):
                    the_extension = getattr(mynifits, anext.lower())
                    if hasattr(the_extension, "__info__"):
                        st.write(the_extension.__info__())
                    st.write("## Extension object:")
                    st.write(the_extension)
                    if hasattr(the_extension, "header"):
                        st.write("## Header : \n" + the_extension.header.__repr__())
            else:
                with st.expander(anext+" - Absent"):
                    st.write(f"No extension {anext}")

    with combiner_tab:
        abe = be.NI_Backend(mynifits)
        abe.create_fov_function_all()
        st.write("## Combiner representation")
        if abe.nifits.ni_iotags is not None:
            check_iotags = st.checkbox("Plot the combiner IOs (requires graphviz)")
            if check_iotags:
                try :
                    import graphviz
                except ImportError:
                    print("Could not find installed graphviz")
                agraph = abe.make_combiner_graph()
                st.graphviz_chart(agraph)
        else:
            st.write("""Could not find a usable ``NI_IOTAGS`` extension
                (It is not mandatory)""")
                

    with trans_tab: # A tab to explore the transmission map (transfer function)

        st.write("# Transfer function of the instrument")

        with st.sidebar:
            use_diffout = st.checkbox("Differential output:", on_change=trigger_rerun)
            rerun = st.button("Recompute")
            if rerun:
                del st.session_state.z
            else:
                pass
    

            if not use_diffout:
                available_outputs = np.arange(mynifits.ni_catm.shape[-2])
                ker_mode_string = "raw output"
            else :
                available_outputs = np.arange(mynifits.ni_kmat.shape[-2])
                ker_mode_string = "kernel output"

            output_maps = st.multiselect(f"Select which {ker_mode_string}", available_outputs,
                                    default=0)
            show_array = st.checkbox("Show array", value=True)

        fov_cols = st.columns(2)
        with fov_cols[0]:
            n_points = st.number_input("Number of points", value=1000, on_change=trigger_rerun)
        with fov_cols[1]:
            max_sep = st.number_input("Max separation", value=100., on_change=trigger_rerun)
        display_cols = st.columns(2)
        with display_cols[0]:
            msizeinc = st.number_input("Marker size", value=1.0, min_value=0., max_value=10.)
            from kernuller.kernel_cm import bbr, bo, vdg
            cmaps_div = ["coolwarm", "seismic", bbr, bo, vdg]
            cmaps_std = ["viridis", "inferno", "magma", "plasma", "gray"]
            if use_diffout:
                mycmap = st.selectbox("Colormap:", options=cmaps_div)
            else:
                mycmap = st.selectbox("Colormap:", options=cmaps_std)

        if output_maps is not None:
            with display_cols[1]:
                mode = st.selectbox("Mode", ["Uniform disk", "Raster", "None"],
                                    on_change=trigger_rerun)
            if mode == "Uniform disk":
                start_time = time()
                acollec = be.PointCollection.from_uniform_disk(max_sep, n_points)
            elif mode == "Raster":
                start_time = time()
                acollec = be.PointCollection.from_centered_square_grid(max_sep, n_points)
            if mode is not "None":
                if "z" not in st.session_state:
                    z = abe.get_all_outs(*acollec.coords_rad, kernels=use_diffout)
                    st.session_state["z"] = z
                else:
                    z = st.session_state.z
                end_time = time()
                st.session_state["time_maps"] = end_time - start_time
                with st.sidebar:
                    st.write(f"Computed in {st.session_state["time_maps"]:.2f} s")
                    st.write(f"Output shape is : {z.shape}")

            wls = mynifits.oi_wavelength.lambs
            min_wl = np.min(wls)
            max_wl = np.max(wls)
            wl_target = st.slider("Wavelength", format="%.2f", step=0.01 ,  min_value=min_wl*1e6, max_value=max_wl*1e6)
            wl_index = np.argmin(np.abs(wls - wl_target * 1e-6))
            st.write(f"Wavelength targeted {wl_target:.2e} m found index {wl_index} at {wls[wl_index]:.2e} m")


            frame_index = st.slider("Frame", min_value=0,
                            max_value=len(mynifits.ni_mod.data_table) - 1)
            if mode is not None:
                if show_array:
                    ncols = 2
                else:
                    ncols = 1
                cols = st.columns(ncols)
                with cols[0]:
                    st.write(f"Frame {frame_index}")
                    for i, out_index in enumerate(output_maps):
                        fig = plt.figure()
                        # plt.scatter(*acollec.coords, c=z[frame_index,wl_index,out_index,:],
                        #         cmap=mycmap, s=marksiz)
                        # plt.gca().set_aspect("equal")
                        # plt.colorbar()
                        # plt.xlabel("Relative position [mas]")
                        mytitle = f"{ker_mode_string} {out_index} for frame {frame_index}"
                        acollec.plot_frame(z, frame_index=frame_index, wl_index=wl_index,
                                out_index=out_index, mycmap=mycmap, marksize_increase=msizeinc,)
                        plt.tight_layout()
                        st.pyplot(fig)
                if show_array:
                    with cols[1]:
                        st.write(f"Frame {frame_index}")
                        if show_array:
                            fig_array = plt.figure(figsize=(5,4), dpi=100)
                            for i, atelxy in enumerate(mynifits.ni_mod.appxy[frame_index]):
                                plt.scatter(*atelxy, s=100)
                            plt.gca().set_aspect("equal")
                            plt.xlabel("Aperture projected position [m]")
                            plt.tight_layout()
                            st.pyplot(fig_array, use_container_width=False)

                if (mynifits.ni_kcov is not None) and (use_diffout):
                    covmat = plt.figure()
                    plt.imshow(mynifits.ni_kcov.data_array[0])
                    plt.xlabel("Differential observable index")
                    plt.colorbar()
                    plt.title(f"The covariance matrix [{mynifits.ni_kcov.unit}]")
                    st.pyplot(covmat)
    with collect_tab:
        check_plot_recording = st.checkbox("Plot the recorded intensities?")
        if check_plot_recording:
            maxval = st.number_input("Plot clipping :", value=None)
            for i in output_maps:
                afig = plt.figure()
                abe.plot_barcode(i, diffout=use_diffout, valminmax=maxval)
                st.pyplot(afig)
                
        check_plot_times = st.checkbox("Plot the time of acquisitions?")
            
        
        if check_plot_times:
            mymjds = np.array(mynifits.ni_mod.data_table["MJD"])
            st.write("Not implemented")
            for ajd in mymjds:
                st.write(ajd)
            # from datetime import datetime
            # fig_times, time_list = plot_on_off_times(file_list, headers=all_headers,
            #                         colors=colors, group_labels=group_labels)
            # # show_and_save(fig_times, "Timeline")
            # show_and_save(fig_times, "timeline")
        from astropy.time import Time as APTime
        mod_tab = mynifits.ni_mod.data_table["MJD"]
        mod_times = APTime(mod_tab.data, format="mjd")
        for atime in mod_times:
            st.write(f"{atime.isot} (mjd={atime})")

        if hasattr(mynifits, "ni_mod"):
            ntel = mynifits.ni_mod.data_table["MOD_PHAS"][0].shape[-1]
        else:
            ntel = 0
        xtel = np.arange(ntel)
        wls_x = (wls-wls[0])/(wls[-1] - wls[0])
        st.write(wls_x)
        check_plot_mods = st.checkbox("Plot the modulation diagram?")
        if check_plot_mods:
            mod_fig = plt.figure()
            for arow in mynifits.ni_mod.data_table:
                plt.text(-4., arow["MJD"], APTime(arow["MJD"], format="mjd").isot)
                full_wls = [axtel + wls  for axtel in xtel]
                for i, arow in enumerate(mynifits.ni_mod.data_table):
                    for j, atel in enumerate(xtel):
                        myc, mys = mod2cs(arow["MOD_PHAS"][:,j])
                        plt.scatter(atel + wls_x, np.ones_like(wls_x)*arow["MJD"],
                                    s=mys, c=myc, marker="s",
                                    vmin=0, vmax=1,
                                    cmap="gist_rainbow")
            for atel in xtel:
                plt.axvline(atel, color="k", linewidth=0.5)
            plt.axvline(ntel, color="k", linewidth=0.5)
            plt.colorbar()
            plt.tight_layout()
            st.pyplot(mod_fig)

        ############################################################
        ## Plot of the actual recorded flux ########################
        ############################################################
        check_plot_recorded = st.checkbox("Plot the recorded nulls?")
        if check_plot_recorded:
            # mycmap = "viridis"
            myoutputs = None
            myrowcols = None
            myresx = 1000
            myresy = 1000
            fig_recorded, fig_axarr = abe.plot_recorded(
                cmap=mycmap, outputs=myoutputs, nrows_ncols=myrowcols,
                res_x=myresx, res_y=myresy
            )
            st.pyplot(fig_recorded)

    with combination:
        from kernuller.diagrams import plot_chromatic_matrix, plot_outputs_smart
        from kernuller.diagrams import colortraces, colortraces_0


        x_inj = abe.nifits.ni_fov.xy2phasor(np.array([0,]), np.array([0,]), md=np)
        x_mod = abe.get_modulation_phasor()

        fig_throughput = plt.figure()
        for i in output_maps:
            kappa = np.abs(abe.nifits.ni_catm.M[:,i,:])
            st.write(kappa.shape)
            if hasattr(abe.nifits , "ni_iotags"):
                if abe.nifits.ni_iotags is not None:
                    out_tag = abe.nifits.ni_iotags.output_type(i)
            else :
                out_tag = ""
            inj_throughput = np.abs(x_inj[frame_index,:,0])
            mod_throughput = np.abs(x_mod[frame_index,:,:])
            kappa = np.sum(kappa[:,:] * mod_throughput[:,:], axis=1)
            output_label = f"Out {i} {out_tag}"
            plt.plot(abe.nifits.oi_wavelength.lambs, kappa, label=output_label)    
        plt.xlabel("Wavelength [m]")
        plt.ylabel(f"Equivalent total collecting power [$m^2$]")
        plt.title("Total equivalent collecting power of at outputs")
        plt.ylim(0,None)
        plt.legend()
        st.pyplot(fig_throughput)
            
        color_blind_mode = st.checkbox("Color blind mode", value=False)
        if color_blind_mode:
            myctrace = colortraces
        else:
            myctrace = colortraces_0
        mycatm = mynifits.ni_catm.M
        if hasattr(abe.nifits, "ni_iotags"):
            if abe.nifits.ni_iotags is not None:
                mylabels = [f"{i} {abe.nifits.ni_iotags.output_type(i)}"
                                        for i in range(mycatm.shape[1])]
        else:
            mylabels = [f"Out {i}" for i in range(mycatm.shape[1])]
        for i in range(10):
            mylabels.append(None)

        st.write("## Assuming no input modulation")
        fig3, axs, matrix = plot_chromatic_matrix(mycatm,
                                                 None, mynifits.oi_wavelength.lambs,
                                                 colors=myctrace,
                                                 verbose=False, returnmatrix=True, minfrac=0.9,
                                                 plotout=False, show=False, title="Combiner complex representation",
                                                 out_label=mylabels)
        fig3.show()
        st.pyplot(fig3)
        st.write("## With the included modulation:")
        st.write("Not implemented yet")
        pass

# In the case no file was provided:
else:
    st.write("Please select a file for viewing")

