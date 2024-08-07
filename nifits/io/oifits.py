"""
A module for reading/writing NIFITS files and handling the data.

To open an existing NIFITS file, use ``nifits.from_nifits`` constructor.

To save an NIFITS object to a file, use ``nifits.to_nifits`` method.

A summary of the information in the oifits object can be obtained by
using the info() method:

   > import oifits
   > oifitsobj = oifits.open('foo.fits')
   > oifitsobj.info()

For further information, contact R. Laugier

"""

import numpy as np
from astropy.io import fits
import astropy.units as u
from astropy.table import Table
from astropy.coordinates import EarthLocation
import datetime
import warnings
from packaging import version

import sys
from dataclasses import dataclass, field
from numpy.typing import ArrayLike

_mjdzero = datetime.datetime(1858, 11, 17)

matchtargetbyname = False
matchstationbyname = False
refdate = datetime.datetime(2000, 1, 1)

def _plurals(count):
    if count != 1: return 's'
    return ''

def array_eq(a: ArrayLike,
              b: ArrayLike):
    """
    Test whether all the elements of two arrays are equal.

    Args:
        a: one input.
        b: another input.
    """

    if len(a) != len(b):
        return False
    try:
        return not (a != b).any()
    except:
        return not (a != b)



def _isnone(x):
    """Convenience hack for checking if x is none; needed because numpy
    arrays will, at some point, return arrays for x == None."""

    return type(x) == type(None)

def _notnone(x):
    """Convenience hack for checking if x is not none; needed because numpy
    arrays will, at some point, return arrays for x != None."""

    return type(x) != type(None)




class OI_STATION(object):
    """ This class corresponds to a single row (i.e. single
    station/telescope) of an OI_ARRAY table."""

    def __init__(self, tel_name=None, sta_name=None, diameter=None, staxyz=[None, None, None], fov=None, fovtype=None, revision=1):

        if revision > 2:
            warnings.warn('OI_ARRAY revision %d not implemented yet'%revision, UserWarning)

        self.revision = revision
        self.tel_name = tel_name
        self.sta_name = sta_name
        self.diameter = diameter
        self.staxyz = staxyz

        if revision >= 2:
            self.fov = fov
            self.fovtype = fovtype
        else:
            self.fov = self.fovtype = None

    def __eq__(self, other):

        if type(self) != type(other): return False

        return not (
            (self.revision != other.revision) or
            (self.tel_name != other.tel_name) or
            (self.sta_name != other.sta_name) or
            (self.diameter != other.diameter) or
            (not _array_eq(self.staxyz, other.staxyz)) or
            (self.fov != other.fov) or
            (self.fovtype != other.fovtype))

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):

        if self.revision >= 2:
            return '%s/%s (%g m, fov %g arcsec (%s))'%(self.sta_name, self.tel_name, self.diameter, self.fov, self.fovtype)
        else:
            return '%s/%s (%g m)'%(self.sta_name, self.tel_name, self.diameter)


        


@dataclass
class NI_CATM(object):
    """Contains the complex amplitude transfer matrix CATM of the instrument.
    The CATM is a complex matrix representing the transformation from the each
    of the complex amplitude of electric field from the inputs to the outputs 
    of the instrument. The dimensions are (n_ch, n_out, n_in) where n_ch 
    represents the spectral channels.
    
    It is expected that
    
    :math:`$\textbf{n}_{out} = \textbf{M}_{CATM}.\textbf{m}_{mod} \circ \textbf{x}_{in}$`
    with :math:`$\textbf{m}_{mod}$` containded in NI_MOD.
    
    """
    Mcatm: ArrayLike
    header: fits.Header

    @classmethod
    def from_hdu(cls, hdu: type(fits.hdu.ImageHDU)):
        """
        Create the NI_CATM object from the HDU extension of an opened fits file.
        """
        Mcatm = hdu.data
        header = hdu.header
        myobj = cls(Mcatm, header)
        return myobj

    def to_hdu(self):
        """
        Returns and hdu object to save into fits
        """
        myhdu = fits.hdu.ImageHDU(data=self.Mcatm)
        myhdu.header = self.header
        return myhdu
    # TODO add a check method


def nulfunc(self, *args, **kwargs):
    raise TypeError


NI_OUT_DEFAULT_HEADER = fits.Header(cards=[("UNITS", "ADU", "The units for output values")])

NI_MOD_DEFAULT_HEADER = fits.Header(cards=[("MOD_PHAS_UNITS", "rad", "The units for modulation phasors"),
                                        ("ARRCOL_UNITS", "m^2", "The units for collecting area")
                                            ])

# Possible to use "chromatic_gaussian_radial", "diameter_gaussian_radial".
# Simplest default is a gaussian with r0 = lambda/D
NI_FOV_DEFAULT_HEADER = fits.Header(cards=[("FOV_MODE","diameter_gaussian_radial","Type of FOV definition"),
                                        ("FOV_offset"),
                                        ("FOV_TELDIAM", 8.0, "diameter of a collecting aperture for FOV"),
                                        ("FOV_TELDIAM_UNIT", "m", ""),
                                        ("WL_SHIFT_MODE", "")])

    

@dataclass
class NI_EXTENSION(object):
    """
    ``NI_EXTENSION`` Generic class for NIFITS extensions

    **Inherited methods:**

    * ``from_hdu``: Creates the object from an ``astropy.io.fits.TableHDU`` object
    * ``to_hdu``  : Returns the ``TableHDU`` from itself.
    """
    data_table: Table = field(default_factory=Table)
    header: fits.Header = field(default_factory=fits.Header)
    # TODO: Potentially, this should be a None by default, while still being a 
    # fits.Header type hint... We can if we have a None, we can catch it with 
    # a __post_init__ method. TODO this will help cleanup the signature in the doc.

    @classmethod
    def from_hdu(cls, hdu: type(fits.hdu.TableHDU)):
        """
        Create the data object from the HDU extension of an opened fits file.
        
        **Arguments:**
        * hdu   : TableHDU object containing the relevant data
        """
        data_table = Table(hdu.data)
        header = hdu.header
        return cls(data_table=data_table, header=header)

    def to_hdu(self):
        """
        Returns and hdu object to save into fits
        
        **Note**: this also updates the header if dimension changes
        """
        # TODO this looks like a bug in astropy.fits: the header should update on its own.
        myhdu = fits.hdu.BinTableHDU(name=self.name, data=self.data_table, header=self.header)
        # myhdu = fits.hdu.BinTableHDU(name=self.name, data=self.data_table)
        
        
        # TODO: fix the diffing?
        # print("Updating header:\n", fits.HeaderDiff(myhdu.header, self.header).__repr__)
        self.header = myhdu.header
        return myhdu

    def __len__(self):
        return len(self.data_table)

@dataclass
class NI_EXTENSION_ARRAY(NI_EXTENSION):
    """
    Generic class for NIFITS array extensions
    """
    data_array: ArrayLike = field(default_factory=np.array)
    header: fits.Header = field(default_factory=fits.Header)

    @classmethod
    def from_hdu(cls, hdu: type(fits.hdu.ImageHDU)):
        """
        Create the data object from the HDU extension of an opened fits file.
        """
        data_array = hdu.data
        header = hdu.header
        return cls(data_array=data_array, header=header)
    
    def to_hdu(self,):
        """
        Returns and hdu object to save into fits
        
        **Note**: this also updates the header if dimension changes
        """
        myhdu = fits.hdu.ImageHDU(name=self.name,data=self.data_array, header=self.header)
        print("Updating header:\n", fits.HeaderDiff(myhdu.header, self.header))
        self.header = myhdu.header
        return myhdu

    def __len__(self):
        pass

@dataclass
class NI_EXTENSION_CPX_ARRAY(NI_EXTENSION):
    """
    Generic class for NIFITS array extensions.

    The array is kept locally as complex valued, but it is
    stored to and loaded from a real-valued array with an
    extra first dimension of length 2 for (real, imaginary) parts.
    """
    data_array: ArrayLike = field(default_factory=np.array)
    header: fits.Header = field(default_factory=fits.Header)

    @classmethod
    def from_hdu(cls, hdu: type(fits.hdu.ImageHDU)):
        """
        Create the data object from the HDU extension of an opened fits file.
        """
        assert hdu.data.shape[0] == 2,\
                f"Data should have 2 layers for real and imag. {hdu.data.shape}"
        data_array = hdu.data[0] + 1j*hdu.data[1]
        header = hdu.header
        return cls(data_array=data_array, header=header)
    
    def to_hdu(self,):
        """
        Returns and hdu object to save into fits
        
        **Note**: this also updates the header if dimension changes
        """
        real_valued_data = np.array([self.data_array.real,
                                    self.data_array.imag], dtype=float)
        myhdu = fits.hdu.ImageHDU(name=self.name,data=real_valued_data, header=self.header)
        print("Updating header:\n", fits.HeaderDiff(myhdu.header, self.header))
        self.header = myhdu.header
        return myhdu

    def __len__(self):
        pass


class OI_ARRAY(NI_EXTENSION):
    __doc__ = """
    ``OI_ARRAY`` definition

    Args:
        data_table: The data to hold
        header: The associated fits header

    
    """ + NI_EXTENSION.__doc__
    name="OI_ARRAY"


from astropy.constants import c as cst_c


class OI_WAVELENGTH(NI_EXTENSION):
    __doc__ = """
    An object storing the OI_WAVELENGTH information, in compatibility with
    OIFITS practices.

    **Shorthands:**

    * ``self.lambs`` : ``ArrayLike`` [m] returns an array containing the center
      of each spectral channel.
    * ``self.dlmabs`` : ``ArrayLike`` [m] an array containing the spectral bin
      widths.
    * ``self.nus`` : ``ArrayLike`` [Hz] an array containing central frequencies
      of the
      spectral channels.
    * ``self.dnus`` : ``ArrayLike`` [Hz] an array containing the frequency bin
      widths.

    """ + NI_EXTENSION.__doc__
    name = "OI_WAVELENGTH"

    @property
    def lambs(self):
        return self.data_table["EFF_WAVE"].data
    @property
    def dlambs(self):
        return self.data_table["EFF_BAND"].data
    @property
    def nus(self):
        return cst_c/self.lambs
    @property
    def dnus(self):
        return cst_c/self.dlambs
        

from dataclasses import field
from typing import List


@dataclass
class OI_TARGET(NI_EXTENSION):
    """
    ``OI_TARGET`` definition.
    """
    # target: List[str] = field(default_factory=list)
    # raep0: float = 0.
    # decep0: float = 0.
    name="OI_TARGET"
    @classmethod
    def from_scratch(cls, ):
        """
        Creates the OI_TARGET object with an empty table.

        **Returns:**
        
        * ``OI_TARGET`` object with an empty table.

        Use ``add_target()`` to finish the job.
        """
        data_table = Table(names=["TARGET_ID", "TARGET", "RAEP0", "DECEP0",
                                    "EQUINOX", "RA_ERR", "DEC_ERR",
                                    "SYSVEL", "VELTYP", "VELDEF",
                                    "PMRA", "PMDEC", "PMRA_ERR", "PMDEC_ERR", 
                                    "PARALLAX", "PARA_ERR", "SPECTYP", "CATEGORY" ],
                            dtype=[int, str, float, float,
                                    float, float, float,
                                    float, str, str,
                                    float, float, float, float, 
                                    float, float, str, str ],)
        return cls(data_table=data_table)
    def add_target(self, target_id=0, target="MyTarget", raep0=0., decep0=0.,
                        equinox=0., ra_err=0., dec_err=0.,
                        sysvel=0., veltyp="", veldef="",
                        pmra=0., pmdec=0., pmra_err=0., pmdec_err=0., 
                        parallax=0., para_err=0., spectyp="", category="" ):
        """
            Use this method to add a row to the table of targets
        **Arguments:**
        
        * param target_id  : (default: 0)
        * ``target``     : (default: "MyTarget")
        * ``raep0``      : (default: 0.)
        * ``decep0``     : (default: 0.)
        * ``equinox``    : (default: 0.)
        * ``ra_err``     : (default: 0.)
        * ``dec_err``    : (default: 0.)
        * ``sysvel``     : (default: 0.)
        * ``veltyp``     : (default: "")
        * ``veldef``     : (default: "")
        * ``pmra``       : (default: 0.)
        * ``pmdec``      : (default: 0.)
        * ``pmra_err``   : (default: 0.)
        * ``pmdec_err``  : (default: 0.)
        * ``parallax``   : (default: 0.)
        * ``para_err``   : (default: 0.)
        * ``spectyp``    : (default: "")
        * ``category``   : (default: "")
            
        """
        self.data_table.add_row(vals=[target_id, target, raep0, decep0,
                                    equinox, ra_err, dec_err,
                                    sysvel, veltyp, veldef,
                                    pmra, pmdec, pmra_err, pmdec_err, 
                                    parallax, para_err, spectyp, category ])


@dataclass
class NI_OUT(NI_EXTENSION):
    __doc__ = """Contains measured intensities of the outputs of the instrument. 
    Dimensions are (n_ch, n_out).""" + NI_EXTENSION.__doc__
    value_out: Table = field(default_factory=Table)
    header: dict = field(default_factory=fits.header)
    name = "NI_OUT"
    
    @property
    def asarray(self, module=np):
        return module.array(self.table_value["u"])

    def check_against_catm(self, catm: NI_CATM):
        n_wl = catm.Mcatm.shape[0]
        # n_inputs = catm.Mcatm.shape[2] # Not needed
        n_outputs = catm.Mcatm.shape[2]
        for i, arow in enumerate(self.table_value):
            assert arow["u"].shape[0] == n_wl,\
                            f"Inconsistent wavelength number in table {i}"
            assert arow["u"].shape[1] == n_outputs,\
                            f"Inconsistent outputs number in table at row {i}"
        assert self.value_output.shape[2] == n_outputs, "Inconsistent output number in array"


@dataclass
class NI_CATM(NI_EXTENSION_CPX_ARRAY):
    __doc__ = """
    The complex amplitude transfre function
    """ + NI_EXTENSION_CPX_ARRAY.__doc__
    name = "NI_CATM"
    @property
    def M(self):
        return self.data_array


class NI_IOUT(NI_EXTENSION):
    __doc__ = """
    ``NI_IOUT`` : a recording of the output values, given in intensity,
    flux, counts or arbitrary units.
    """ + NI_EXTENSION.__doc__
    name = "NI_IOUT"
    @property
    def iout(self):
        return self.data_table["value"].data


class NI_KIOUT(NI_EXTENSION):
    __doc__ = """
    ``NI_KIOUT`` : a recording of the processed output values using the
    the post-processing matrix given by ``NI_KMAT``. Typically differential
    null or kernel-null.
    """ + NI_EXTENSION.__doc__
    name = "NI_KIOUT"
    @property
    def kiout(self):
        return self.data_table["value"].data


class NI_KCOV(NI_EXTENSION_ARRAY):
    __doc__ = """
    The covariance matrix for the processed data contained in KIOUT.
    """ + NI_EXTENSION_ARRAY.__doc__
    name = "NI_KCOV"
    @property
    def kcov(self):
        return self.data_array


@dataclass
class NI_KMAT(NI_EXTENSION_ARRAY):
    __doc__ = """
    The kernel matrix that defines the post-processing operation between outputs.
    The linear combination is defined by a real-valued matrix.
    """ + NI_EXTENSION_ARRAY.__doc__
    name = "NI_KMAT"
    @property
    def K(self):
        return self.data_array


@dataclass
class NI_MOD(NI_EXTENSION):
    r"""
    Contains input modulation vector for the given observation. The format
    is a complex phasor representing the alteration applied by the instrument
    to the light at its inputs. Either an intended modulation, or an estimated
    instrumental error. the dimenstions are (n_ch, n_in)
    
    The effects modeled in NI_MOD must cumulate with some that may be modeled
    in NI_CATM. It is recommended to include in CATM the static effects and in
    NI_MOD any affect that may vary throughout the observµng run.


    :math:`n_a \times \lambda`

    
    .. table:: ``NI_MOD``: The table of time-dependent collectorwise
    information.

       +---------------+----------------------------+------------------+-------------------+
       | Item          | format                     | unit             | comment           |
       +===============+============================+==================+===================+
       | ``APP_INDEX`` |  ``int``                   | NA               | Indices of        |
       |               |                            |                  | subaperture       |
       |               |                            |                  | (starts at 0)     |
       +---------------+----------------------------+------------------+-------------------+
       | ``TARGET_ID`` |  ``int``                   | d                | Index of target   |
       |               |                            |                  | in ``OI_TARGET``  |
       +---------------+----------------------------+------------------+-------------------+
       | ``TIME``      | ``float``                  | s                | Backwards         |
       |               |                            |                  | compatibility     |
       +---------------+----------------------------+------------------+-------------------+
       | ``MJD``       | ``float``                  | day              |                   |
       +---------------+----------------------------+------------------+-------------------+
       | ``INT_TIME``  | ``float``                  | s                | Exposure time     |
       +---------------+----------------------------+------------------+-------------------+
       | ``MOD_PHAS``  | ``n_{wl},n_a`` ``float``   |                  | Complex phasor of |
       |               |                            |                  | modulation for    |
       |               |                            |                  | all collectors    |
       +---------------+----------------------------+------------------+-------------------+
       | ``APPXY``     | ``n_a,2`` ``float``        | m                | Projected         |
       |               |                            |                  | location of       |
       |               |                            |                  | subapertures in   |
       |               |                            |                  | the plane         |
       |               |                            |                  | orthogonal to the |
       |               |                            |                  | line of sight and |
       |               |                            |                  | oriented as       |
       |               |                            |                  | ``(               |
       |               |                            |                  | \alpha, \delta)`` |
       +---------------+----------------------------+------------------+-------------------+
       | ``ARRCOL``    | ``n_a`` ``float``          | ``\mathrm{m}^2`` | Collecting area   |
       |               |                            |                  | of the            |
       |               |                            |                  | subaperture       |
       +---------------+----------------------------+------------------+-------------------+
       | ``FOV_INDEX`` | ``n_a`` ``int``            | NA               | The entry of the  |
       |               |                            |                  | ``NI_FOV`` to use |
       |               |                            |                  | for this          |
       |               |                            |                  | subaperture.      |
       +---------------+----------------------------+------------------+-------------------+

    """
    data_table: Table = field(default_factory=Table)
    header: fits.Header = field(default_factory=fits.Header)
    name = "NI_MOD"

    @property
    def n_series(self):
        return len(self.data_table)

    @property
    def all_phasors(self):
        return self.data_table["MOD_PHAS"].data

    @property
    def appxy(self):
        """Shape n_frames x n_a x 2"""
        return self.data_table["APPXY"].data

    @property
    def dateobs(self):
        """
        Get the dateobs from the weighted mean of the observation time
        from each of the observation times given in the rows of ``NI_MOD``
        table.
        """
        raise NotImplementedError(self.dateobs)
        return None

    @property
    def arrcol(self):
        """
        The collecting area of the telescopes
        """
        return self.data_table["ARRCOL"].data

    @property
    def int_time(self):
        """
        Conveniently retrieve the integration time.
        """
        return self.data_table["INT_TIME"].data
        
        
        
def create_basic_fov_data(D, offset, lamb, n):
    """
    A convenience function to help define the FOV function and data model
    """
    r_0 = (lamb/D)*u.rad.to(u.mas)
    def xy2phasor(x,y, offset):
        r = np.hypot(x[None,:]-offset[:,0], y[None,:]-offset[:,1])
        phasor = np.exp(-(r/r_0)**2)
        return phasor.astype(complex)
    all_offsets = np.zeros((n, lamb.shape[0], 2))
    indices = np.arange(n)
    mytable = Table(names=["INDEX", "offsets"],
                    data=[indices, all_offsets])
    return mytable, xy2phasor

class NI_KCOV(NI_EXTENSION_ARRAY):
    __doc__ = """
    Storing the covariance of the data.
    """ + NI_EXTENSION_ARRAY.__doc__

class NI_FOV(NI_EXTENSION):
    __doc__ = r"""
    The ``NI_FOV`` data containing information of the field of view (vigneting)
    function as a function of wavelength.

    This can be interpreted in different ways depending on the value of the
    header keyword ``FOV_MODE``.

    * ``diameter_gaussian_radial``   : A simple gaussian radial falloff function
      based on a size of :math:`\lambda/D` and a chromatic offset defined for each
      spectral bin. The ``simple_from_header()`` constructor can help create a simple
      extension with 0 offset.
    * More options will come.
    """ + NI_EXTENSION.__doc__
    name = "NI_FOV"
    @classmethod
    def simple_from_header(cls, header=None, lamb=None, n=0):
        r"""
        Constructor for a simple ``NI_FOV`` object with chromatic gaussian profile and 
        no offset.

        **Arguments:**

        * header    : (astropy.io.fits.Header) Header containing the required information
          such as ``FOV_TELDIAM`` and ``FOV_TELDIAM_UNIT`` which are used to create the
          gaussian profiles of radius :math:`\lambda/D`
        """
        offset = np.zeros((n,2))
        telescope_diameter_q = header["FOV_TELDIAM"]*u.Unit(header["FOV_TELDIAM_UNIT"])
        telescope_diameter_m = telescope_diameter_q.to(u.m).value
        mytable, xh2phasor = create_basic_fov_data(telescope_diameter_m, offset=offset,
                                    lamb=lamb, n=n)
        return cls(data_table=mytable, header=header)




    def get_fov_function(self, lamb: ArrayLike, n: int):
        """
        Returns the function to get the chromatic phasor
        given by injection for a the index n of the time series

        **This method will move to the backend**

        **Arguments:**

        * ``lamb`` : ArrayLike the array of wavelength bins
        * ``n``    : int the index of the time series to compute for
        """
        assert self.header["FOV_MODE"] == "diameter_gaussian_radial"
        D = self.header[""]
        r_0 = (lamb/D)*u.rad.to(u.mas)
        offset = self.data_table["offsets"][n]
        def xy2phasor(alpha, beta):
            """
            Returns the phasor for a given position of the field of view

            **Arguments:**

            * ``alpha`` : Position in RA
            * ``beta``  : Position in Dec

            **Returns:** The complex phasor
            """
            r = np.hypot(alpha[None,:]-offset[:,0], beta[None,:]-offset[:,1])
            phasor = np.exp(-(r/r_0)**2)
            return phasor.astype(complex)
        return xy2phasor








# class NI_MOD(object):
#     """Contains input modulation vector for the given observation. The format
#     is a complex phasor representing the alteration applied by the instrument
#     to the light at its inputs. Either an intended modulation, or an estimated
#     instrumental error. the dimenstions are (n_ch, n_in)
#     
#     The effects modeled in NI_MOD must cumulate with some that may be modeled
#     in NI_CATM. It is recommended to include in CATM the static effects and in
#     NI_MOD any affect that may vary throughout the observing run."""
#     def __init__(self, app_index, target_id, time, mjd,
#                 int_time, mod_phas, app_xy, arrcol,
#                 fov_index):
#         self.app_index = app_index
#         self.target_id = target_id
#         self.time = time
#         self.mjd = mjd
#         self.int_time = int_time
#         self.app_xy = app_xy
#         self.arrcol = arrcol
#         self.fov_index = fov_index
#         self.mod_phas = mod_phas


NIFITS_EXTENSIONS = np.array(["OI_ARRAY",
                    "OI_WAVELENGTH",
                    "NI_CATM",
                    "NI_FOV",
                    "NI_KMAT",
                    "NI_MOD",
                    "NI_IOUT",
                    "NI_KIOUT",
                    "NI_KCOV"])

NIFITS_KEYWORDS = []

STATIC_EXTENSIONS = [True,
                    True,
                    True,
                    True,
                    False,
                    False,
                    False,
                    False,
                    False]

def getclass(classname):
    return getattr(sys.modules[__name__], classname)

@dataclass
class nifits(object):
    """Class representation of the nifits object."""
    header: fits.Header = None
    ni_catm: NI_CATM = None
    ni_fov: NI_FOV = None
    ni_kmat: NI_KMAT = None
    oi_wavelength: OI_WAVELENGTH = None
    oi_target: OI_TARGET = None
    ni_mod: NI_MOD = None
    ni_iout: NI_IOUT = None
    ni_kiout: NI_KIOUT = None
    ni_kcov: NI_KCOV = None

    

    @classmethod
    def from_nifits(cls, filename: str):
        """
        Create the nifits object from the HDU extension of an opened fits file.
        """
        if isinstance(filename, fits.hdu.hdulist.HDUList):
            hdulist = filename
        else:
            hdulist = fits.open(filename)
            
        obj_dict = {}
        header = hdulist["PRIMARY"].header
        obj_dict["header"] = header
        for anext in NIFITS_EXTENSIONS:
            if hdulist.__contains__(anext):
                theclass = getclass(anext)
                theobj = theclass.from_hdu(hdulist[anext])
                obj_dict[anext.lower()] = theobj
            else:
                print(f"Missing {anext}")
        print("Checking header", isinstance(header, fits.Header))
        print("contains_header:", obj_dict.__contains__("header"))
        return cls(**obj_dict)

    def to_nifits(self, filename:str = "",
                        static_only: bool = False,
                        dynamic_only: bool = False,
                        static_hash: str = "",
                        writefile: bool = True,
                        overwrite: bool = False):
        """
        Write the extension objects to a nifits file.

        **Arguments**: 

        * `static_only` :  (bool) only save the extensions corresponding
          to static parameters of the model (NI_CATM and NI_FOV). 
          Default: False
        * `dynamic` only : (bool) only save the dynamic extensions. If true,
          the hash of the static file should be passed as `static_hash`.
          Default: False
        * `static_hash` : (str) The hash of the static file.
          Default: ""

        """
        # TODO: Possibly, the static_hash should be a dictionary with
        # a hash for each extension
        hdulist = fits.HDUList()
        hdu = fits.PrimaryHDU()
        if static_only:
            extension_list = NIFITS_EXTENSIONS[STATIC_EXTENSIONS]
        elif dynamic_only:
            extension_list = NIFITS_EXTENSIONS[np.logical_not(STATIC_EXTENSIONS)]
        else:
            extension_list = NIFITS_EXTENSIONS
        hdulist.append(hdu)
        for anext in extension_list:
            print(anext, hasattr(self,anext.lower()))
            if hasattr(self, anext.lower()):
                print(anext.lower(), flush=True)
                theobj = getattr(self, anext.lower())
                thehdu = theobj.to_hdu()
                hdulist.append(thehdu)
                hdu.header[anext] = "Included"
                # TODO Possibly we need to do this differently:
                # TODO Maybe pass the header to the `to_hdu` method?
            else:
                hdu.header[anext] = "Not included"
                print(f"Warning: Could not find the {anext} object")
        print(hdu.header)
        if writefile:
            hdulist.writeto(filename, overwrite=overwrite)
            return hdulist
        else:
            return hdulist












