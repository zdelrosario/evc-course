__all__ = [
    "make_hull",
    "hull_data",
    "hull_rotate",
    "get_avs",
    "get_mass_properties",
    "get_moment_curve",
    "get_buoyant_properties",
    "get_equ_waterline",
    "RHO_WATER",
    "fun_avs",
    "fun_moment",
    "fun_performance",
    "var_correct",
]

from numpy import array, average, argmin, concatenate, linspace, meshgrid, sum, max, min, isfinite, trapz
from numpy import abs, sin, cos, pi, NaN, nanmax, nanmin
from pandas import concat, DataFrame
from scipy.optimize import bisect
from warnings import catch_warnings, simplefilter

# Global constants
RHO_WATER = 0.03613 # Density of water (lb / in^3)
RHO_0 = 0.04516 # Filament density (lb / in^3)
G = 386 # Gravitational acceleration (in / s^2)

## Reference stuff
# --------------------------------------------------
var_correct = ["H", "W", "n", "d", "f_com"]

## Boat generator
# --------------------------------------------------
def make_hull(X):
    r"""

    Args:
        X (iterable): [H, W, n, d, f_com] = X

          H     = height of boat [in]
          W     = width of boat [in]
          n     = shape parameter [-]
          d     = displacement ratio [-]
                = weight of boat / weight of max displaced water
          f_com = height of COM from bottom, as frac of H [-]

    Returns:
        DataFrame: Hull points
        DataFrame: Mass properties
    """
    H, W, n, d, f_com = X
    y_com = H * f_com

    f_hull = lambda x: H * abs(2 * x / W)**n
    g_top = lambda x, y: y <= H
    rho_hull = lambda x, y: d * RHO_WATER

    df_hull, dx, dy = hull_data(
        f_hull,
        g_top,
        rho_hull,
        n_marg=100,
    )

    df_mass = get_mass_properties(df_hull, dx, dy)
    # Override COM
    df_mass.x = 0
    df_mass.y = y_com

    return df_hull, df_mass

## Hull manipulation
# --------------------------------------------------
def hull_data(f_hull, g_top, rho_hull, n_marg=50, x_wid=3, y_lo=+0, y_hi=+4):
    r"""
    Args:
        f_hull (lambda): Function of signature y = f(x);
            defines lower surface of boat
        g_top (lambda): Function of signature g (bool) = g(x, y);
            True indicates within boat
        rho_hull (lambda): Function of signature rho = rho(x, y);
            returns local hull density

    Returns:
        DataFrame: x, y, dm boat hull points and element masses
        float: dx
        float: dy
    """
    Xv = linspace(-x_wid, +x_wid, num=n_marg)
    Yv = linspace(y_lo, y_hi, num=n_marg)
    dx = Xv[1] - Xv[0]
    dy = Yv[1] - Yv[0]

    Xm, Ym = meshgrid(Xv, Yv)
    n_tot = Xm.shape[0] * Xm.shape[1]

    Z = concatenate(
        (Xm.reshape(n_tot, -1), Ym.reshape(n_tot, -1)),
        axis=1,
    )

    M = array([rho_hull(x, y) * dx * dy for x, y in Z])

    I_hull = [
        (f_hull(x) <= y) & g_top(x, y)
        for x, y in Z
    ]
    Z_hull = Z[I_hull]
    M_hull = M[I_hull]

    df_hull = DataFrame(dict(
        x=Z_hull[:, 0],
        y=Z_hull[:, 1],
        dm=M_hull,
    ))

    return df_hull, dx, dy

def hull_rotate(df_hull, df_mass, angle):
    r"""
    Args:
        df_hull (DataFrame): Hull points
        df_mass (DataFrame): Mass properties, gives COM
        angle (float, radians): Heel angle

    Returns:
        DataFrame: Hull points rotated about COM
    """
    R = array([
        [cos(angle), -sin(angle)],
        [sin(angle),  cos(angle)]
    ])
    Z_hull_r = (
        df_hull[["x", "y"]].values - df_mass[["x", "y"]].values
    ).dot(R.T) + df_mass[["x", "y"]].values

    return DataFrame(dict(
        x=Z_hull_r[:, 0],
        y=Z_hull_r[:, 1],
        dm=df_hull.dm,
    ))

## Evaluate hull
# --------------------------------------------------
def get_width(X, y_w):
    H, W, n, d, f_com = X
    x_w = 0.5 * W * (y_w / H) ** (1 / n)

    return x_w

def get_mass_properties(df_hull, dx, dy):
    x_com = average(df_hull.x, weights=df_hull.dm)
    y_com = average(df_hull.y, weights=df_hull.dm)
    mass = df_hull.dm.sum()

    return DataFrame(dict(
        x=[x_com],
        y=[y_com],
        dx=[dx],
        dy=[dy],
        mass=[mass]
    ))

def get_buoyant_properties(df_hull_rot, df_mass, y_water):
    r"""
    Args:
        df_hull_rot (DataFrame): Rotated hull points
        df_mass (DataFrame): Mass properties
        y_water (float): Location of waterline (in absolute coordinate system)
    """
    dx = df_mass.dx[0]
    dy = df_mass.dy[0]

    I_under = df_hull_rot.y <= y_water
    x_cob = average(df_hull_rot[I_under].x)
    y_cob = average(df_hull_rot[I_under].y)

    m_water = RHO_WATER * sum(I_under) * dx * dy
    F_net = (m_water - df_mass.mass[0]) * G
    M_net = G * m_water * (x_cob - df_mass.x[0])
    # Righting moment == opposite true moment?
    ## Could just use moment arm

    return DataFrame(dict(
        x_cob=[x_cob],
        y_cob=[y_cob],
        F_net=[F_net],
        M_net=[M_net],
    ))

def get_equ_waterline(df_hull, df_mass, angle, y_l=-4, y_h=4):
    r"""
    Args:
        df_hull (DataFrame): Unrotated hull points
        df_mass (DataFrame): Mass properties
        angle (float): Angle of rotation
        y_l (float): Low-bound for waterline
        y_h (float): High-bound for waterline

    Returns:
        float: Waterline of zero net vertical force (heave-steady)
    """
    dx = df_mass.dx[0]
    dy = df_mass.dy[0]

    df_hull_r = hull_rotate(df_hull, df_mass, angle)

    def fun(y_g):
        df_buoy = get_buoyant_properties(
            df_hull_r,
            df_mass,
            y_g,
        )

        return df_buoy.F_net[0]

    try:
        with catch_warnings():
            simplefilter("ignore")
            y_star = bisect(fun, y_l, y_h, maxiter=1000)

        df_res = get_buoyant_properties(
                df_hull_r,
                df_mass,
                y_star,
            )
        df_res["y_w"] = y_star
    except ValueError:
        df_res = DataFrame(dict(y_cob=[NaN], M_net=[NaN], y_w=[NaN]))

    return df_res

def get_moment_curve(df_hull, df_mass, a_l=0, a_h=pi, num=50):
    r"""Generate a righting moment curve

    Args:
        df_hull (DataFrame): Unrotated hull points
        df_mass (DataFrame): Mass properties
        a_l (float): Low-bound for angle
        a_h (float): High-bound for angle
        num (int): Number of points to sample (linearly) between a_l, a_h

    Returns:
        DataFrame: Data from angle sweep
    """
    df_res = DataFrame()
    a_all = linspace(a_l, a_h, num=num)

    for angle in a_all:
        df_tmp = get_equ_waterline(df_hull, df_mass, angle)
        df_tmp["angle"] = angle

        df_res = concat((df_res, df_tmp), axis=0)
    df_res.reset_index(inplace=True, drop=True)

    return df_res

def get_avs(df_hull, df_mass, a_l=0.1, a_h=pi - 0.1):
    r"""
    Args:
        df_hull (DataFrame): Unrotated hull points
        df_mass (DataFrame): Mass properties
        a_l (float): Low-bound for angle
        a_h (float): High-bound for angle

    Returns:
        float: Angle of vanishing stability
    """
    # Create helper function
    def fun(angle):
        df_res = get_equ_waterline(
            df_hull,
            df_mass,
            angle,
        )

        return df_res.M_net[0]

    # Bisect for zero-moment
    try:
        a_star = bisect(fun, a_l, a_h, maxiter=1000)

        df_res = get_equ_waterline(
            df_hull,
            df_mass,
            a_star,
        )
        df_res["angle"] = a_star
    except ValueError:
        df_res = DataFrame(dict(angle=[NaN]))

    return df_res

## Convenience Functions
# --------------------------------------------------
def fun_avs(X, num=15):
    r"""Compute AVS of boat design, stably

    For numerical stability, find a lower bracket for the AVS then run bisection.

    Args:
        X (iterable): [H, W, n, d, f_com] = X

          H     = height of boat [in]
          W     = width of boat [in]
          n     = shape parameter [-]
          d     = displacement ratio [-]
                = weight of boat / weight of max displaced water
          f_com = height of COM from bottom, as frac of H [-]

        num (int): number of points for moment sweep; should be coarse (num < ~20)

    Returns:
        float: Angle of vanishing stability
    """
    ## Generate boat hull given parameters
    df_hull, df_mass = make_hull(X)

    ## Generate coarse moment curve to find a bracket for AVS
    df_moment = get_moment_curve(df_hull, df_mass, num=num)

    ## Find lowest bracket for root (AVS)
    try:
        ind_h = next(i for i, df in df_moment[1:].iterrows() if df.M_net > 0)
    except StopIteration:
        return NaN

    a_h = df_moment.iloc[ind_h].angle
    a_l = df_moment.iloc[ind_h - 1].angle

    ## Use the bracket to find AVS
    df_avs = get_avs(df_hull, df_mass, a_l=a_l, a_h=a_h)

    return df_avs.angle[0]

def fun_moment(X, num=50):
    r"""Compute net moment curve

    Args:
        X (iterable): [H, W, n, d, f_com] = X

          H     = height of boat [in]
          W     = width of boat [in]
          n     = shape parameter [-]
          d     = displacement ratio [-]
                = weight of boat / weight of max displaced water
          f_com = height of COM from bottom, as frac of H [-]

        num (int): number of points for moment sweep

    Returns:
        df: Moment curve
    """
    ## Generate boat hull given parameters
    df_hull, df_mass = make_hull(X)

    ## Generate coarse moment curve to find a bracket for AVS
    df_moment = get_moment_curve(df_hull, df_mass, num=num)

    return df_moment

def fun_performance(X, num=30):
    r"""Compute several boat design performance characteristics

    Args:
        X (iterable): [H, W, n, d, f_com] = X

          H     = height of boat [in]
          W     = width of boat [in]
          n     = shape parameter [-]
          d     = displacement ratio [-]
                = weight of boat / weight of max displaced water
          f_com = height of COM from bottom, as frac of H [-]

        num (int): number of points for moment sweep

    Returns:
        df: Performance characteristics
    """
    ## Generate boat hull given parameters
    df_hull, df_mass = make_hull(X)

    ## Generate moment curve
    df_moment = get_moment_curve(df_hull, df_mass, num=num)

    ## FIND AVS
    ## Find lowest bracket for root (AVS)
    try:
        ind_h = next(i for i, df in df_moment[1:].iterrows() if df.M_net > 0)
        a_h = df_moment.iloc[ind_h].angle
        a_l = df_moment.iloc[ind_h - 1].angle

        ## Use the bracket to find AVS
        df_res = get_avs(df_hull, df_mass, a_l=a_l, a_h=a_h)
    except StopIteration:
        df_res = DataFrame(dict(angle=[NaN]))

    ## COMPUTE INITIAL METACENTRIC HEIGHT
    df_waterline = get_equ_waterline(df_hull, df_mass, 0)
    x_w = get_width(X, df_waterline["y_w"])
    I = (2 * x_w)**3 / 12        # in^3
    V = df_mass.mass / RHO_WATER # in^2
    BM = I / V
    GB = df_mass.y - df_waterline.y_cob
    df_res["GM"] = BM - GB
    df_res["mass"] = df_mass.mass

    ## FIND DERIVATIVES
    df_res["dMdtheta_0"] = (
        (df_moment.M_net[1] - df_moment.M_net[0])
      / (df_moment.angle[1] - df_moment.angle[0])
    )
    if isfinite(df_res.angle[0]):
        # Index nearest to AVS
        ind_avs = argmin(abs(df_moment.angle - df_res.angle[0]))
        df_res["dMdtheta_avs"] = (
            (df_moment.M_net[ind_avs+1] - df_moment.M_net[ind_avs])
          / (df_moment.angle[ind_avs+1] - df_moment.angle[ind_avs])
        )
        df_res["int_M_stable"] = trapz(
            df_moment.M_net[0:ind_avs],
            x=df_moment.angle[0:ind_avs]
        )
    else:
        df_res["dMdtheta_avs"] = NaN
        df_res["int_M_stable"] = trapz(df_moment.M_net, x=df_moment.angle)

    ## FIND MAX / MIN
    df_res["M_max"] = nanmax(df_moment.M_net)
    df_res["M_min"] = nanmin(df_moment.M_net)

    return df_res[[
        "mass",
        "GM",
        "angle",
        "dMdtheta_0",
        "dMdtheta_avs",
        "M_max",
        "M_min",
        "int_M_stable"
    ]]
